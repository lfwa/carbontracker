# Aggregating log files
**carbontracker** supports aggregating all log files in a specified directory to a single estimate of the carbon footprint.


#### Example usage
```python
from carbontracker import parser

parser.print_aggregate(log_dir="./my_log_directory/")
```
#### Example output
```
The training of models in this work is estimated to use 4.494 kWh of electricity contributing to 0.423 kg of CO2eq. This is equivalent to 3.515 km travelled by car. Measured by carbontracker (https://github.com/lfwa/carbontracker).
```

### Convert logs to dictionary objects
Log files can be parsed into dictionaries using `parser.parse_all_logs()` or `parser.parse_logs()`.
#### Example usage
```python
from carbontracker import parser

logs = parser.parse_all_logs(log_dir="./logs/")
first_log = logs[0]

print(f"Output file name: {first_log['output_filename']}")
print(f"Standard file name: {first_log['standard_filename']}")
print(f"Stopped early: {first_log['early_stop']}")
print(f"Measured consumption: {first_log['actual']}")
print(f"Predicted consumption: {first_log['pred']}")
print(f"Measured GPU devices: {first_log['components']['gpu']['devices']}")
```
#### Example output
```
Output file name: ./logs/2020-05-17T19:02Z_carbontracker_output.log
Standard file name: ./logs/2020-05-17T19:02Z_carbontracker.log
Stopped early: False
Measured consumption: {'epochs': 1, 'duration (s)': 8.0, 'energy (kWh)': 6.5e-05, 'co2eq (g)': 0.019201, 'equivalents': {'km travelled by car': 0.000159}}
Predicted consumption: {'epochs': 3, 'duration (s)': 25.0, 'energy (kWh)': 1000.000196, 'co2eq (g)': 10000.057604, 'equivalents': {'km travelled by car': 10000.000478}}
Measured GPU devices: ['Tesla T4']
```
