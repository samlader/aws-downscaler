# AWS Downscaler

Scale down AWS resources during non-work hours to save costs. Inspired by the brilliant [kube-downscaler](https://codeberg.org/hjacobs/kube-downscaler).

- Currently the following AWS resource types:
  - EC2 Auto Scaling Groups
  - ECS Services
- Flexible scheduling with timezone support
- Resource exclusion via tags
- Grace periods for newly created resources
- Dry-run mode for testing

> [!CAUTION]
> This project is a WIP and is not production ready.

## Installation

1. Install:
```bash
pip install .
```

1. Configure AWS credentials:
```bash
export AWS_ACCESS_KEY_ID=your_access_key
export AWS_SECRET_ACCESS_KEY=your_secret_key
export AWS_REGION=your_region
```

1. Run the downscaler:
```bash
aws-downscaler --default-uptime="Mon-Fri 08:00-18:00 America/New_York"
```

## Configuration

### Time Specifications

Time definitions accept a comma-separated list of specifications in two formats:

1. Recurring specifications:
```
<WEEKDAY-FROM>-<WEEKDAY-TO-INCLUSIVE> <HH>:<MM>-<HH>:<MM> <TIMEZONE>
```
Example: `Mon-Fri 07:30-20:30 America/New_York`

2. Absolute specifications:
```
<YYYY>-<MM>-<DD>T<HH>:<MM>:<SS>[+-]<TZHH>:<TZMM>
```
Example: `2024-04-01T08:00:00-04:00`

### Resource Tags

Resources can be configured using AWS tags:

- `downscaler:uptime`: Override uptime schedule
- `downscaler:downtime`: Override downtime schedule
- `downscaler:exclude`: Exclude resource from scaling
- `downscaler:exclude-until`: Temporarily exclude until timestamp
- `downscaler:downtime-scale`: Override downtime scale factor

### Command Line Options

- `--dry-run`: Print actions without making changes
- `--debug`: Enable debug logging
- `--once`: Run once and exit
- `--interval`: Loop interval in seconds (default: 60)
- `--default-uptime`: Default uptime schedule
- `--default-downtime`: Default downtime schedule
- `--grace-period`: Grace period for new resources in seconds
- `--include-resources`: Resource types to manage (comma-separated)
- `--exclude-resources`: Resource patterns to exclude (comma-separated)
- `--downtime-scale`: Scale factor during downtime (0-100, default: 0)

### Example Usage

Scale down all resources outside work hours:
```bash
aws-downscaler --default-uptime="Mon-Fri 08:00-18:00 America/New_York"
```

Scale down specific resource types:
```bash
aws-downscaler --include-resources="asg,ecs"
```

## Contributions

Contributions and bug reports are welcome! Feel free to open issues, submit pull requests or contact me if you need any support.

## License

This project is licensed under the [MIT License](LICENSE).