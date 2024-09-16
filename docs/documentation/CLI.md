# CLI
::: carbontracker.cli.main
<line>
### Usage

To start tracking, simply run the following command:

```bash
carbontracker <script_or_command> <arg1> <arg2> --log_dir <log_directory> --api_keys <api_keys>
```
For example:
```bash
carbontracker python train_resnet.py --epochs 100 --step_size 1 --log_dir ./logs --api_keys '{"electricitymaps": "YOUR_KEY_HERE"}'
```

### Arguments

- `--log_dir`: Specifies the directory where CarbonTracker will save the logs. This is useful for keeping a record of your runs and for later analysis.
- `--api_keys`: API key(s) for external services used by CarbonTracker to retrieve real-time carbon intensity data. Currently, [Electricity Maps](https://www.electricitymaps.com/) is supported

### Additional Options
Log Parsing: If you've previously run CarbonTracker and saved the logs, you can parse and aggregate the data for analysis. Use the following command to aggregate logs from a specific directory:
```bash
carbontracker --parse <log_directory>
```
For example:

```bash
carbontracker --parse ./logs
```


