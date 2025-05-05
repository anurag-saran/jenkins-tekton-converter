# Jenkins to Tekton Converter with Validation and Refinement

## Overview
This Python project converts Jenkins pipeline files (`*.jenkinsfile`, `*.jenkins`, `*.groovy`) into Tekton Pipeline YAML using OpenAI's language models. It includes a multi-step process:
1.  **Jenkins to JSON:** Converts the input Jenkinsfile into a structured JSON representation using an LLM (`gpt-3.5-turbo`).
2.  **JSON to Tekton:** Converts the JSON representation into an initial Tekton Pipeline YAML using an LLM (`gpt-3.5-turbo`) and the `src/prompts/json2tekton.txt` prompt.
3.  **First Validation:** Validates the initial Tekton YAML using an LLM (`gpt-3.5-turbo`) and the `src/prompts/validate_tekton_pipeline.txt` prompt. It generates a validation report and potentially an improved version of the Tekton YAML.
4.  **Second Validation:** Performs a second validation pass on the *improved* YAML from the previous step, using an LLM (`gpt-3.5-turbo`) and the `src/prompts/fix_tekton_pipeline.txt` prompt, aiming for final corrections.
5.  **Logging:** Records validation reports from both steps into `tekton_validation_errors.log`.
6.  **Prompt Refinement (Optional):** Uses the `tekton_validation_errors.log` and the current `src/prompts/json2tekton.txt` prompt to ask a more advanced LLM (`gpt-4o`) to refine the `json2tekton.txt` prompt for potentially better future conversions. This step is controlled by the `--refine-prompt` flag and includes automatic versioning of the prompt file.

## Prerequisites
- Python 3.8+
- OpenAI Python library (`pip install openai`)
- OpenAI API Key

## Setup
1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd jenkins-tekton-converter
   ```
2. Create and activate a virtual environment (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Configure your OpenAI API Key:
   - Copy `.env.example` to `.env`:
     ```bash
     cp .env.example .env
     ```
   - Edit the `.env` file and add your OpenAI API key:
     ```
     OPENAI_API_KEY='your_openai_api_key_here'
     ```
   The script will load the key from this file.

## Project Structure
```
jenkins-tekton-converter/
├── src/
│   ├── converter.py          # Main conversion, validation, and refinement script
│   └── prompts/
│       ├── jenkins2json.txt       # System prompt for Jenkins -> JSON conversion
│       ├── json2tekton.txt        # System prompt for JSON -> Tekton conversion (refined over time)
│       ├── validate_tekton_pipeline.txt # System prompt for 1st Tekton validation/improvement
│       └── fix_tekton_pipeline.txt    # System prompt for 2nd Tekton validation/fixing
├── jenkins_files/           # Place your input Jenkins pipeline files here
├── tekton_pipelines/        # Directory for generated output files
├── .env                     # Stores your OpenAI API key (DO NOT COMMIT)
├── .env.example             # Example .env file
├── .gitignore
├── README.md
├── requirements.txt
├── run_counter.txt          # Tracks the run number for file prefixes
└── tekton_validation_errors.log # Logs validation feedback from conversion runs
```

## Usage
1. Place your Jenkins pipeline files (e.g., `my_pipeline.jenkinsfile`) in the `jenkins_files/` directory.
2. Run the conversion script from the project root directory:

   **To run conversion and validation WITHOUT prompt refinement:**
   ```bash
   python3 src/converter.py
   ```

   **To run conversion and validation AND refine the `json2tekton.txt` prompt:**
   ```bash
   python3 src/converter.py --refine-prompt
   ```

   **Optional arguments:**
   * `--input-dir`: Specify a different input directory (default: `./jenkins_files`)
   * `--output-dir`: Specify a different output directory (default: `./tekton_pipelines`)
   * `--log-file`: Specify a different path for the validation log (default: `./tekton_validation_errors.log`)

3. Check the `tekton_pipelines/` directory for output files. For each input file (e.g., `j2.jenkinsfile`) and run number (e.g., `9`), you will find:
   - `9-j2.json`: The intermediate JSON representation.
   - `9-j2-tekton-pipeline.yaml`: The initial Tekton pipeline generated from JSON.
   - `9-validated-j2-tekton-pipeline.yaml`: The Tekton pipeline after the first validation/improvement step.
   - `9-validated2-j2-tekton-pipeline.yaml`: The Tekton pipeline after the second validation/fixing step.

4. Review the `tekton_validation_errors.log` file for detailed reports from the validation steps.

5. If you used `--refine-prompt`, check `src/prompts/` for the updated `json2tekton.txt` and its versioned backup (e.g., `json2tekton_v1.txt`, `json2tekton_v2.txt`, etc.).

## Conversion & Validation Process
- The script iterates through each compatible file in the input directory.
- Each file undergoes the Jenkins -> JSON -> Tekton conversion steps.
- The generated Tekton YAML is then passed through two validation stages using specific prompts (`validate_tekton_pipeline.txt`, `fix_tekton_pipeline.txt`).
- Each stage uses the LLM to identify issues and suggest fixes, attempting to produce a more compliant and correct Tekton file.
- Validation reports (including identified issues and suggestions) are logged to `tekton_validation_errors.log`.
- Intermediate and final files are saved with a run number prefix (e.g., `9-`) in the output directory.

## Automatic Prompt Refinement
- When the `--refine-prompt` flag is used, after all files are processed, the script triggers a refinement step for the `src/prompts/json2tekton.txt` prompt.
- It reads the entire `tekton_validation_errors.log` generated during the *current* run.
- It reads the *current* `src/prompts/json2tekton.txt`.
- It sends both the log content and the current prompt to `gpt-4o` with instructions to improve the prompt based on the feedback in the logs.
- Before overwriting `json2tekton.txt` with the response from `gpt-4o`, it creates a versioned backup (e.g., `json2tekton_v1.txt`).
- This allows the `json2tekton.txt` prompt to iteratively improve over multiple runs, adapting to common errors identified during validation.

## Notes
- Requires an active OpenAI API key with sufficient credits.
- Conversion and validation quality depend heavily on the LLM's interpretation and the quality of the prompts. Manual review and adjustment of the final Tekton YAML (`validated2-*.yaml`) are often necessary.
- The prompt refinement process aims to improve future conversions but is also AI-driven and may require monitoring.
- Ensure your `.env` file is included in your `.gitignore` to prevent accidentally committing your API key.
