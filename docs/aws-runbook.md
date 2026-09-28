# AWS testbed runbook

Two VMs in Hyderabad (`ap-south-2`), in one cluster placement group (SoT §10):

| VM | Type | Role |
|---|---|---|
| client | c7i.4xlarge (16 vCPU, 32 GiB) | benchmark runner and crypto client: the system under test |
| server | c7i.2xlarge (8 vCPU, 16 GiB) + 200 GB gp3 | MinIO (source build, host networking) |

Cost: about $1.1/hour while both run; disks about $30/month even when stopped. Everything is
tagged `Project=pqc-bench`. Keep the AWS budget alarm on.

## Once per project

```bash
infra/aws/pqc-aws.sh check       # free: identity, vCPU quota, instance types, AMI
infra/aws/pqc-aws.sh up          # creates the VMs: billing starts
infra/aws/pqc-aws.sh provision   # ~15 min: installs everything, runs the test suite on the client
infra/aws/pqc-aws.sh baseline    # iperf3 network + fio disk baselines
```

`provision` deploys the **committed** code (`git archive HEAD`). Commit before provisioning, and
provision again after changing code.

## Each experiment

```bash
infra/aws/pqc-aws.sh start               # if stopped
infra/aws/pqc-aws.sh run config/pilot.yaml
infra/aws/pqc-aws.sh logs                # Ctrl-C only stops following; the run continues
infra/aws/pqc-aws.sh fetch               # copy experiments/ to this laptop
make validate-results RUN=experiments/pilot/<stamp>
```

The run continues if your laptop sleeps or disconnects (tmux on the client).

## Cost guards

- The client stops itself 2 minutes after an experiment ends (`NO_AUTOSTOP=1` disables this).
- Both VMs stop themselves after 60 minutes with no benchmark activity.
- `infra/aws/pqc-aws.sh stop` stops both immediately; stopped VMs bill only for disks.
- `infra/aws/pqc-aws.sh destroy` removes every resource the script created (asks you to type `destroy`).

## Security

- SSH is open only to the public IP you ran `up` from. If your IP changes, add the new one in the
  EC2 console (security group `pqc-bench-sg`) or run `destroy` and `up` again.
- The SSH key is `~/.ssh/pqc-bench.pem` and never enters the repository.
- MinIO credentials are generated during `provision` and exist only on the two VMs.
- MinIO and its metrics are reachable only between the two VMs (security-group rule).

## Troubleshooting

- `InsufficientInstanceCapacity` on `up`: set `PLACEMENT=none` or another `AZ` in
  `infra/aws/config.env`, run `destroy`, then `up`.
- SSH times out: your public IP changed (see Security).
- CPU frequency pinning is not available on non-metal EC2 sizes; variation is handled with
  repetitions and randomized order (SoT §9.3), and the instance type is recorded in every run manifest.
