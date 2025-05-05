# Jenkins to Tekton Converter

## Overview
This Python project converts Jenkins pipeline files to Tekton pipeline YAML using OpenAI's language model.

## Prerequisites
- Python 3.8+
- OpenAI API Key

## Setup
1. Clone the repository
2. Create a virtual environment
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Copy `.env.example` to `.env` and add your OpenAI API key

## Project Structure
```
jenkins-tekton-converter/
├── src/
│   ├── converter.py       # Main conversion script
│   └── prompts/
│       ├── jenkins2json.txt  # System prompt for Jenkins to JSON conversion
│       └── json2tekton.txt   # System prompt for JSON to Tekton conversion
├── config.yaml         # Configuration file for API keys and settings
├── jenkins_files/        # Place your Jenkins pipeline files here
├── tekton_pipelines/     # Converted Tekton pipeline files will be saved here
├── requirements.txt
└── .env
```

## Usage
1. Set your OpenAI API key in `.env`
2. Place your Jenkins pipeline files in the `jenkins_files/` directory
   - Supported file extensions: `.jenkins`, `.groovy`, `Jenkinsfile*`
3. Run the conversion:
```
python src/converter.py
```
4. Find converted Tekton pipeline files in the `tekton_pipelines/` directory

## Customization
### Prompts
- Edit `src/prompts/jenkins2json.txt` to modify Jenkins to JSON conversion behavior
- Edit `src/prompts/json2tekton.txt` to modify JSON to Tekton conversion behavior

### Configuration
Use `config.yaml` to customize various aspects of the converter:
- Set OpenAI API key
- Configure input/output directories
- Adjust logging settings
- Specify supported file extensions

#### Configuration Options
```yaml
openai:
  api_key: your_api_key  # Can also use .env
  model: gpt-3.5-turbo

conversion:
  input_directory: jenkins_files
  output_directory: tekton_pipelines
  supported_extensions:
    - .jenkinsfile
    - .jenkins
    - .groovy

logging:
  level: INFO  # DEBUG, INFO, WARNING, ERROR
  file: conversion.log  # Optional log file

error_handling:
  continue_on_file_error: true
  max_retries: 3
```

## Batch Conversion
- The script automatically processes all Jenkins files in the input directory
- Each file is converted to a separate Tekton pipeline YAML
- Conversion errors for individual files will not stop the entire batch process

## Notes
- Requires an active OpenAI API key
- Conversion is based on AI interpretation and may need manual refinement
- Supports basic Jenkins pipeline to Tekton conversion
