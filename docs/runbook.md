# Runbook

## 1) Generate TLS certs

```bash
./scripts/host/generate_certs.sh
```

## 2) Run an experiment

```bash
./scripts/run/run_experiment.sh baseline
```

Other configs:

- area_sweep
- fragmentation_sweep
- brightness_sweep
- watermark_pattern

Example:

```bash
./scripts/run/run_experiment.sh watermark_pattern
```

## 3) Validate outputs

```bash
./scripts/validate/check_outputs.sh
```

## 4) Host-side capture (optional)

Use host tools to capture Docker bridge traffic while the experiment runs.

```bash
# Example only; pick the correct interface for your machine
sudo tcpdump -i any -w data/pcaps/exp_capture.pcap tcp port 8443
```
