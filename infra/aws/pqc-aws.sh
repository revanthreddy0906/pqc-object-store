#!/usr/bin/env bash
# AWS testbed for the final measurements (SoT §10): one client VM and one MinIO VM
# in the same cluster placement group. Run from anywhere on your laptop.
#
#   infra/aws/pqc-aws.sh check       read-only: credentials, quota, instance types (free)
#   infra/aws/pqc-aws.sh up          create key pair, firewall, placement group, 2 VMs  (COSTS MONEY)
#   infra/aws/pqc-aws.sh provision   copy the repo to both VMs and install everything
#   infra/aws/pqc-aws.sh update      push newly committed code (fast; keeps builds and data)
#   infra/aws/pqc-aws.sh baseline    network (iperf3) and disk (fio) baselines
#   infra/aws/pqc-aws.sh run CONFIG  start an experiment on the client in tmux (survives logout)
#   infra/aws/pqc-aws.sh logs        follow the running experiment
#   infra/aws/pqc-aws.sh fetch       copy experiments/ back to this laptop
#   infra/aws/pqc-aws.sh ssh client|server
#   infra/aws/pqc-aws.sh status      state, IPs and hourly cost
#   infra/aws/pqc-aws.sh stop|start  stopped VMs bill only for disks; start resumes
#   infra/aws/pqc-aws.sh destroy     terminate VMs and delete everything this script created
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
source "$HERE/config.env"
STATE="$HERE/state.env"          # git-ignored: instance ids and IPs
KEY_FILE="$HOME/.ssh/${KEY_NAME}.pem"
AWS=(aws --region "$REGION" --output text)
SSH_OPTS=(-i "$KEY_FILE" -o StrictHostKeyChecking=accept-new -o ServerAliveInterval=30)
TAGS="{Key=Project,Value=$PROJECT_TAG}"

die() { echo "error: $*" >&2; exit 1; }
load_state() { [[ -f "$STATE" ]] || die "no testbed yet; run: $0 up"; source "$STATE"; }
save_state() { while (($#)); do printf '%s=%q\n' "$1" "$2" >> "$STATE"; shift 2; done; }
public_ip() { "${AWS[@]}" ec2 describe-instances --instance-ids "$1" \
  --query 'Reservations[0].Instances[0].PublicIpAddress'; }
remote() { local host=$1; shift; ssh "${SSH_OPTS[@]}" "ubuntu@$host" "$@"; }

ubuntu_ami() {
  "${AWS[@]}" ec2 describe-images --owners 099720109477 \
    --filters "Name=name,Values=ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-*" \
              "Name=state,Values=available" \
    --query 'sort_by(Images,&CreationDate)[-1].ImageId'
}

cmd_check() {
  command -v aws >/dev/null || die "aws CLI not found (brew install awscli)"
  echo "identity : $(aws sts get-caller-identity --query Arn --output text)"
  echo "region   : $REGION ($AZ)"
  local quota need
  quota="$("${AWS[@]}" service-quotas get-service-quota --service-code ec2 \
    --quota-code L-1216C47A --query 'Quota.Value' 2>/dev/null || echo unknown)"
  need=24
  echo "vCPU quota (On-Demand Standard): $quota, needed $need"
  echo "offered types: $("${AWS[@]}" ec2 describe-instance-type-offerings --location-type availability-zone \
    --filters "Name=location,Values=$AZ" "Name=instance-type,Values=$CLIENT_TYPE,$SERVER_TYPE" \
    --query 'InstanceTypeOfferings[].InstanceType')"
  echo "ubuntu AMI : $(ubuntu_ami)"
  [[ -f "$STATE" ]] && echo "state.env exists: a testbed is already recorded (see status)"
  return 0
}

cmd_up() {
  [[ -f "$STATE" ]] && die "state.env exists: a testbed is already up (use status or destroy)"
  command -v aws >/dev/null || die "aws CLI not found"
  local my_ip ami vpc subnet sg
  my_ip="$(curl -fsS https://checkip.amazonaws.com | tr -d '[:space:]')"
  ami="$(ubuntu_ami)"; [[ "$ami" == ami-* ]] || die "could not find the Ubuntu 24.04 AMI"
  vpc="$("${AWS[@]}" ec2 describe-vpcs --filters Name=isDefault,Values=true --query 'Vpcs[0].VpcId')"
  [[ "$vpc" == vpc-* ]] || die "no default VPC in $REGION"
  subnet="$("${AWS[@]}" ec2 describe-subnets --filters "Name=vpc-id,Values=$vpc" \
    "Name=availability-zone,Values=$AZ" --query 'Subnets[0].SubnetId')"
  [[ "$subnet" == subnet-* ]] || die "no default subnet in $AZ"

  echo "Creating in $REGION ($AZ): $CLIENT_TYPE client + $SERVER_TYPE server, ${DATA_GB} GB data disk"
  echo "Ubuntu AMI $ami; SSH allowed only from $my_ip; ~\$${HOURLY_USD}/h while running"
  : > "$STATE"
  save_state REGION "$REGION" AZ "$AZ"

  if [[ ! -f "$KEY_FILE" ]]; then
    mkdir -p "$HOME/.ssh"
    "${AWS[@]}" ec2 create-key-pair --key-name "$KEY_NAME" --key-type ed25519 \
      --tag-specifications "ResourceType=key-pair,Tags=[$TAGS]" \
      --query KeyMaterial > "$KEY_FILE"
    chmod 600 "$KEY_FILE"
    save_state CREATED_KEY 1
  fi

  sg="$("${AWS[@]}" ec2 create-security-group --group-name "$PROJECT_TAG-sg" --vpc-id "$vpc" \
    --description "pqc-object-store benchmark: SSH from one IP, all traffic between the two VMs" \
    --tag-specifications "ResourceType=security-group,Tags=[$TAGS]" --query GroupId)"
  save_state SG_ID "$sg"
  "${AWS[@]}" ec2 authorize-security-group-ingress --group-id "$sg" \
    --protocol tcp --port 22 --cidr "$my_ip/32" >/dev/null
  "${AWS[@]}" ec2 authorize-security-group-ingress --group-id "$sg" \
    --ip-permissions "IpProtocol=-1,UserIdGroupPairs=[{GroupId=$sg}]" >/dev/null

  local pg_args=()
  if [[ "$PLACEMENT" == cluster ]]; then
    "${AWS[@]}" ec2 create-placement-group --group-name "$PROJECT_TAG-pg" --strategy cluster \
      --tag-specifications "ResourceType=placement-group,Tags=[$TAGS]" >/dev/null
    save_state PG_NAME "$PROJECT_TAG-pg"
    pg_args=(--placement "GroupName=$PROJECT_TAG-pg")
  fi

  launch() {  # role type root_gb [extra block-device json]
    local role=$1 type=$2 root_gb=$3 extra=${4:-}
    local bdm="[{\"DeviceName\":\"/dev/sda1\",\"Ebs\":{\"VolumeSize\":$root_gb,\"VolumeType\":\"gp3\",\"DeleteOnTermination\":true}}$extra]"
    "${AWS[@]}" ec2 run-instances --image-id "$ami" --instance-type "$type" --count 1 \
      --key-name "$KEY_NAME" --subnet-id "$subnet" --security-group-ids "$sg" \
      ${pg_args[@]+"${pg_args[@]}"} --block-device-mappings "$bdm" \
      --metadata-options "HttpTokens=required,HttpEndpoint=enabled" \
      --instance-initiated-shutdown-behavior stop \
      --tag-specifications "ResourceType=instance,Tags=[$TAGS,{Key=Name,Value=$PROJECT_TAG-$role},{Key=Role,Value=$role}]" \
                           "ResourceType=volume,Tags=[$TAGS]" \
      --query 'Instances[0].InstanceId'
  }
  local data_disk=",{\"DeviceName\":\"/dev/sdf\",\"Ebs\":{\"VolumeSize\":$DATA_GB,\"VolumeType\":\"gp3\",\"Iops\":$DATA_IOPS,\"Throughput\":$DATA_MBPS,\"DeleteOnTermination\":true}}"
  local server client
  server="$(launch server "$SERVER_TYPE" 30 "$data_disk")"; save_state SERVER_ID "$server"
  client="$(launch client "$CLIENT_TYPE" 60)";              save_state CLIENT_ID "$client"
  echo "Waiting for both instances to run..."
  "${AWS[@]}" ec2 wait instance-running --instance-ids "$server" "$client"
  save_state SERVER_PRIVATE_IP "$("${AWS[@]}" ec2 describe-instances --instance-ids "$server" \
    --query 'Reservations[0].Instances[0].PrivateIpAddress')"
  cmd_status
  echo "Next: $0 provision   (give the VMs ~1 minute to accept SSH)"
}

cmd_status() {
  load_state
  "${AWS[@]}" --output table ec2 describe-instances --instance-ids "$SERVER_ID" "$CLIENT_ID" \
    --query 'Reservations[].Instances[].{Role:Tags[?Key==`Role`]|[0].Value,Type:InstanceType,State:State.Name,PublicIP:PublicIpAddress,PrivateIP:PrivateIpAddress}'
  echo "Approximate cost: ~\$${HOURLY_USD}/h while both run; disks ~\$${DISK_USD_MONTH}/month even when stopped"
}

cmd_ssh() { load_state; local id=$CLIENT_ID; [[ "${1:-client}" == server ]] && id=$SERVER_ID
  ssh "${SSH_OPTS[@]}" "ubuntu@$(public_ip "$id")"; }

cmd_provision() {
  load_state
  local server_ip client_ip bundle password
  server_ip="$(public_ip "$SERVER_ID")"; client_ip="$(public_ip "$CLIENT_ID")"
  if [[ -n "$(git -C "$REPO" status --porcelain --untracked-files=no)" ]]; then
    echo "warning: uncommitted changes are NOT deployed; only commit $(git -C "$REPO" rev-parse --short HEAD) is"
  fi
  bundle="$(mktemp -d)/pqc.tar.gz"
  git -C "$REPO" archive --format=tar.gz -o "$bundle" HEAD   # committed code only
  local commit; commit="$(git -C "$REPO" rev-parse HEAD)"
  password="$(openssl rand -hex 24)"   # MinIO credentials live only on the two VMs
  for host in "$server_ip" "$client_ip"; do
    scp "${SSH_OPTS[@]}" "$bundle" "ubuntu@$host:pqc.tar.gz" >/dev/null
    remote "$host" "rm -rf pqc && mkdir pqc && tar -xzf pqc.tar.gz -C pqc && rm pqc.tar.gz \
      && echo $commit > pqc/GIT_COMMIT"
  done
  remote "$server_ip" "cd pqc && MINIO_ROOT_PASSWORD=$password bash scripts/setup_vm.sh server"
  remote "$client_ip" "cd pqc && MINIO_ROOT_PASSWORD=$password SERVER_IP=$SERVER_PRIVATE_IP bash scripts/setup_vm.sh client"
  rm -f "$bundle"
  echo "Provisioned. Next: $0 baseline"
}

cmd_update() {  # push committed code only; keeps builds, .env and experiments on the VMs
  load_state
  if [[ -n "$(git -C "$REPO" status --porcelain --untracked-files=no)" ]]; then
    echo "warning: uncommitted changes are NOT deployed; only commit $(git -C "$REPO" rev-parse --short HEAD) is"
  fi
  local bundle commit; bundle="$(mktemp -d)/pqc.tar.gz"; commit="$(git -C "$REPO" rev-parse HEAD)"
  git -C "$REPO" archive --format=tar.gz -o "$bundle" HEAD
  for id in "$SERVER_ID" "$CLIENT_ID"; do
    local host; host="$(public_ip "$id")"
    scp "${SSH_OPTS[@]}" "$bundle" "ubuntu@$host:pqc.tar.gz" >/dev/null
    remote "$host" "tar -xzf pqc.tar.gz -C pqc && rm pqc.tar.gz && echo $commit > pqc/GIT_COMMIT"
  done
  rm -f "$bundle"
  echo "Updated both VMs to $(git -C "$REPO" rev-parse --short HEAD)"
}

cmd_baseline() {
  load_state
  local server_ip; server_ip="$(public_ip "$SERVER_ID")"
  remote "$(public_ip "$CLIENT_ID")" "cd pqc && bash scripts/setup_vm.sh baseline $SERVER_PRIVATE_IP"
  remote "$server_ip" "cd pqc && bash scripts/setup_vm.sh fio"
  mkdir -p "$REPO/experiments/baselines"
  scp "${SSH_OPTS[@]}" "ubuntu@$server_ip:pqc/experiments/baselines/*" "$REPO/experiments/baselines/" >/dev/null
  echo "Disk baseline copied to experiments/baselines/ (network baseline arrives with: $0 fetch)"
}

cmd_run() {
  load_state
  local config=${1:?usage: $0 run config/pilot.yaml}
  remote "$(public_ip "$CLIENT_ID")" "cd pqc && mkdir -p experiments && tmux new-session -d -s bench \
    'bash scripts/setup_vm.sh run $config $SERVER_PRIVATE_IP 2>&1 | tee -a experiments/bench.log'"
  echo "Started $config in tmux session 'bench' on the client. Follow with: $0 logs"
  echo "The client stops itself 10 minutes after the experiment ends; the server after 60 idle minutes."
}

cmd_logs() { load_state; remote "$(public_ip "$CLIENT_ID")" "tail -n 50 -f pqc/experiments/bench.log"; }

cmd_fetch() {
  load_state
  mkdir -p "$REPO/experiments"
  rsync -az -e "ssh ${SSH_OPTS[*]}" \
    "ubuntu@$(public_ip "$CLIENT_ID"):pqc/experiments/" "$REPO/experiments/"
  echo "Copied into experiments/. Validate with: make validate-results RUN=experiments/<id>/<stamp>"
}

cmd_stop()  { load_state; "${AWS[@]}" ec2 stop-instances --instance-ids "$SERVER_ID" "$CLIENT_ID" >/dev/null
  echo "Stopping. Disks are kept (~\$${DISK_USD_MONTH}/month); compute billing stops."; }
cmd_start() {
  load_state
  local id state
  for id in "$SERVER_ID" "$CLIENT_ID"; do   # a VM still shutting down cannot be started yet
    state="$("${AWS[@]}" ec2 describe-instances --instance-ids "$id" --query 'Reservations[0].Instances[0].State.Name')"
    if [[ "$state" == stopping || "$state" == shutting-down ]]; then
      echo "$id is $state; waiting for it to stop first..."
      "${AWS[@]}" ec2 wait instance-stopped --instance-ids "$id"
    fi
  done
  "${AWS[@]}" ec2 start-instances --instance-ids "$SERVER_ID" "$CLIENT_ID" >/dev/null
  "${AWS[@]}" ec2 wait instance-running --instance-ids "$SERVER_ID" "$CLIENT_ID"; cmd_status; }

cmd_destroy() {
  load_state
  echo "This terminates both VMs and deletes their disks, the firewall, placement group and key pair."
  echo "Run '$0 fetch' first if you need the data. Type 'destroy' to continue:"
  read -r answer; [[ "$answer" == destroy ]] || die "cancelled"
  "${AWS[@]}" ec2 terminate-instances --instance-ids "$SERVER_ID" "$CLIENT_ID" >/dev/null
  "${AWS[@]}" ec2 wait instance-terminated --instance-ids "$SERVER_ID" "$CLIENT_ID"
  [[ -n "${PG_NAME:-}" ]] && "${AWS[@]}" ec2 delete-placement-group --group-name "$PG_NAME"
  "${AWS[@]}" ec2 delete-security-group --group-id "$SG_ID"
  if [[ -n "${CREATED_KEY:-}" ]]; then
    "${AWS[@]}" ec2 delete-key-pair --key-name "$KEY_NAME"; rm -f "$KEY_FILE"
  fi
  rm -f "$STATE"
  echo "Everything created by this script is gone."
}

case "${1:-}" in
  check) cmd_check ;; up) cmd_up ;; provision) cmd_provision ;; update) cmd_update ;;
  baseline) cmd_baseline ;;
  run) shift; cmd_run "$@" ;; logs) cmd_logs ;; fetch) cmd_fetch ;;
  ssh) shift; cmd_ssh "$@" ;; status) cmd_status ;;
  stop) cmd_stop ;; start) cmd_start ;; destroy) cmd_destroy ;;
  *) sed -n '2,18p' "$0"; exit 1 ;;
esac
