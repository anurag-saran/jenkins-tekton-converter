import os
import yaml
import logging
import json
import glob
import re
import shutil
import argparse
from datetime import datetime
from dotenv import load_dotenv
import openai
from openai import OpenAI

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Counter file path
COUNTER_FILE = "run_counter.txt"
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # Get project root
COUNTER_FILE_PATH = os.path.join(PROJECT_ROOT, COUNTER_FILE)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


def refine_json2tekton_prompt(log_file_path, prompt_file_path):
    """
    Uses the validation feedback log to refine the json2tekton prompt via an LLM call.

    :param log_file_path: Path to the tekton_validation_errors.log file.
    :param prompt_file_path: Path to the src/prompts/json2tekton.txt file.
    :return: True if successful, False otherwise.
    """
    logger.info(f"Starting prompt refinement for {os.path.basename(prompt_file_path)} using feedback from {os.path.basename(log_file_path)}")

    try:
        # --- 1. Read Log File Content ---
        if not os.path.exists(log_file_path):
            logger.error(f"Log file not found: {log_file_path}")
            return False
        with open(log_file_path, 'r') as f:
            log_content = f.read()
        if not log_content.strip():
            logger.warning(f"Log file {log_file_path} is empty. Skipping prompt refinement.")
            return True # Not an error, just nothing to do

        # --- 2. Read Current Prompt Content ---
        if not os.path.exists(prompt_file_path):
            logger.error(f"Prompt file not found: {prompt_file_path}")
            return False
        with open(prompt_file_path, 'r') as f:
            current_prompt = f.read()

        # --- 3. Initialize OpenAI Client --- 
        # Reusing API key loading logic structure
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            try:
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                config_path = os.path.join(project_root, 'config.yaml')
                if os.path.exists(config_path):
                    with open(config_path, 'r') as cfg_file:
                        config = yaml.safe_load(cfg_file)
                        api_key = config.get('openai', {}).get('api_key')
                    if api_key:
                        logger.info("Loaded API key from config.yaml for prompt refinement")
            except Exception as cfg_e:
                logger.error(f"Error reading config.yaml for API key during refinement: {cfg_e}")
        
        if not api_key:
            error_msg = "OpenAI API key missing for prompt refinement. Set OPENAI_API_KEY or add to config.yaml."
            logger.error(error_msg)
            return False

        client = OpenAI(api_key=api_key)

        # --- 4. Construct Refinement Prompt for LLM ---
        refinement_system_prompt = ("You are an expert prompt engineer. Your task is to refine a system prompt used for converting structured JSON into Tekton Pipeline YAML. "
                                  "You will be given the original prompt and feedback/validation reports generated from Tekton YAML produced using that original prompt. "
                                  "Analyze the feedback and modify the original prompt to address the issues raised in the feedback, aiming to generate higher quality, more compliant Tekton YAML in the future. "
                                  "Output ONLY the refined prompt text. Do not include any explanations, greetings, or markdown formatting around the prompt text.")
        
        refinement_user_message = (f"Original Prompt:\n```text\n{current_prompt}\n```\n\n"
                                 f"Validation Feedback Log:\n```log\n{log_content}\n```\n\n"
                                 f"Based on the Validation Feedback Log, please refine the Original Prompt. Remember to output ONLY the refined prompt text.")

        # --- 5. Call LLM for Refinement --- 
        logger.info("Sending request to LLM for prompt refinement...")
        try:
            response = client.chat.completions.create(
                model="gpt-4o", # Using a more capable model for prompt engineering might yield better results
                messages=[
                    {"role": "system", "content": refinement_system_prompt},
                    {"role": "user", "content": refinement_user_message}
                ],
                temperature=0.5 # Lower temperature for more focused refinement
            )
            refined_prompt = response.choices[0].message.content.strip()
            logger.info("Received refined prompt from LLM.")

        except Exception as api_e:
            logger.error(f"Error calling OpenAI API for prompt refinement: {api_e}")
            return False

        # --- 6. Validate and Write Refined Prompt --- 
        if not refined_prompt:
            logger.error("LLM returned an empty response for the refined prompt.")
            return False

        # --- 6. Version existing prompt --- 
        try:
            prompt_dir = os.path.dirname(prompt_file_path)
            base_name = os.path.splitext(os.path.basename(prompt_file_path))[0]
            version_pattern = os.path.join(prompt_dir, f"{base_name}_v*.txt")
            existing_versions = glob.glob(version_pattern)
            
            max_version = 0
            for version_file in existing_versions:
                match = re.search(r'_v(\d+)\.txt$', version_file)
                if match:
                    max_version = max(max_version, int(match.group(1)))
            
            next_version = max_version + 1
            backup_file_path = os.path.join(prompt_dir, f"{base_name}_v{next_version}.txt")
            
            # Copy current prompt to versioned backup
            if os.path.exists(prompt_file_path):
                shutil.copy2(prompt_file_path, backup_file_path)
                logger.info(f"Backed up current prompt to {backup_file_path}")
            else:
                 logger.warning(f"Original prompt file {prompt_file_path} not found for backup.")

        except Exception as backup_e:
            logger.error(f"Error backing up existing prompt file {prompt_file_path}: {backup_e}")
            # Continue to writing the new prompt even if backup fails, but log error

        # --- 7. Write Refined Prompt --- 
        try:
            with open(prompt_file_path, 'w') as f:
                f.write(refined_prompt)
            logger.info(f"Successfully updated prompt file: {prompt_file_path}")
            return True
        except Exception as write_e:
            logger.error(f"Error writing refined prompt to {prompt_file_path}: {write_e}")
            return False
            
    except Exception as e:
        logger.error(f"An unexpected error occurred during prompt refinement: {e}")
        return False


class JenkinsTektonConverter:
    def __init__(self, config_path=None):
        # Load configuration
        if config_path is None:
            config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.yaml')
        
        with open(config_path, 'r') as config_file:
            self.config = yaml.safe_load(config_file)
        
        # Initialize OpenAI API key
        api_key = os.getenv('OPENAI_API_KEY') or self.config['openai']['api_key']
        if not api_key:
            raise ValueError("OpenAI API key is missing. Please set in .env or config.yaml")
        
        # Configure logging
        logging.basicConfig(
            level=getattr(logging, self.config['logging']['level'].upper(), logging.INFO),
            format='%(asctime)s - %(levelname)s - %(message)s',
            filename=self.config['logging'].get('file')
        )
        
        # Create OpenAI client
        self.client = OpenAI(api_key=api_key)

    def convert_jenkins_to_json(self, jenkins_file_path):
        """
        Convert Jenkins file to JSON using OpenAI
        
        :param jenkins_file_path: Path to the Jenkins file
        :return: JSON representation of the Jenkins file
        """
        try:
            # Read Jenkins file
            with open(jenkins_file_path, 'r') as file:
                jenkins_content = file.read()
            
            # Read system prompt from file
            with open(os.path.join(os.path.dirname(__file__), 'prompts', 'jenkins2json.txt'), 'r') as prompt_file:
                system_prompt = prompt_file.read()
            
            # Make API call to OpenAI
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Convert this Jenkins file to JSON:\n{jenkins_content}"}
                ]
            )
            
            # Extract JSON from response
            json_content = response.choices[0].message.content.strip()
            
            # Validate JSON
            json.loads(json_content)
            
            logger.info(f"Successfully converted Jenkins file to JSON")
            return json_content
        
        except Exception as e:
            logger.error(f"Error converting Jenkins file to JSON: {e}")
            raise

    def convert_json_to_tekton(self, json_content):
        """
        Convert JSON to Tekton pipeline file
        
        :param json_content: JSON content of the pipeline
        :return: Tekton pipeline YAML
        """
        try:
            # Read system prompt from file
            with open(os.path.join(os.path.dirname(__file__), 'prompts', 'json2tekton.txt'), 'r') as prompt_file:
                system_prompt = prompt_file.read()
            
            # Make API call to OpenAI for Tekton conversion
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Convert this JSON pipeline to Tekton YAML:\n{json_content}"}
                ]
            )
            
            # Extract Tekton YAML from response
            tekton_yaml = response.choices[0].message.content.strip()
            
            logger.info("Successfully converted JSON to Tekton pipeline")
            return tekton_yaml
        
        except Exception as e:
            logger.error(f"Error converting JSON to Tekton pipeline: {e}")
            raise

def validate_tekton_pipeline(tekton_file_path, prompt_file_basename="validate_tekton_pipeline.txt"):
    """
    Validate and improve a Tekton pipeline YAML file using OpenAI.

    :param tekton_file_path: Path to the Tekton pipeline YAML file
    :param prompt_file_basename: The basename of the prompt file to use (e.g., 'validate_tekton_pipeline.txt')
    :return: Tuple (validation_report, fixed_tekton_yaml) or (error_message, None) on failure
    """
    try:
        # --- 1. Load the specified system prompt --- 
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        prompts_dir = os.path.join(project_root, 'src/prompts')
        prompt_file_path = os.path.join(prompts_dir, prompt_file_basename)

        if not os.path.exists(prompt_file_path):
            error_msg = f"Prompt file not found: {prompt_file_path}"
            logger.error(error_msg)
            return f"Error: {error_msg}", None

        with open(prompt_file_path, 'r') as f:
            system_prompt = f.read()
        logger.info(f"Loaded prompt: {prompt_file_basename}")

        # --- 2. Load Tekton pipeline content --- 
        with open(tekton_file_path, 'r') as file:
            tekton_content = file.read()

        # --- 3. Initialize OpenAI Client --- 
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
             # Attempt to load from config.yaml as a fallback (adjust path if needed)
             try:
                 config_path = os.path.join(project_root, 'config.yaml')
                 if os.path.exists(config_path):
                     with open(config_path, 'r') as cfg_file:
                         config = yaml.safe_load(cfg_file)
                         api_key = config.get('openai', {}).get('api_key')
                     if api_key:
                         logger.info("Loaded API key from config.yaml")
                     else:
                          logger.warning("API key not found in config.yaml")
                 else:
                      logger.warning("config.yaml not found, cannot load API key from it.")
             except Exception as cfg_e:
                 logger.error(f"Error reading config.yaml for API key: {cfg_e}")

        if not api_key:
            error_msg = "OpenAI API key is missing. Set OPENAI_API_KEY environment variable or add to config.yaml."
            logger.error(error_msg)
            # Return an error tuple instead of raising an exception
            return f"Configuration Error: {error_msg}", None

        client = OpenAI(api_key=api_key)

        # Make API call to OpenAI for validation and fixing, requesting JSON
        response = client.chat.completions.create(
            model="gpt-3.5-turbo", # Consider allowing model selection via config
            response_format={ "type": "json_object" }, # Request JSON output
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Analyze and validate this Tekton pipeline YAML:\n```yaml\n{tekton_content}\n```"} # Added ```yaml fence for clarity
            ]
        )

        # Extract and parse JSON response
        response_content = response.choices[0].message.content.strip()
        logger.debug(f"Raw validation response for {tekton_file_path}: {response_content}")

        try:
            result_json = json.loads(response_content)
            validation_report = result_json.get('validation_report', 'Validation report missing in response.')
            fixed_tekton_yaml = result_json.get('fixed_tekton_yaml', '# Fixed YAML missing in response.')

            logger.info(f"Successfully validated and processed improvements for {tekton_file_path}")
            return validation_report, fixed_tekton_yaml

        except json.JSONDecodeError as json_e:
            error_msg = f"Failed to parse JSON response from OpenAI for {tekton_file_path}: {json_e}\nRaw Response: {response_content}"
            logger.error(error_msg)
            # Return the raw response as the report, and indicate failure for fixed yaml
            return f"JSON Parse Error: {error_msg}", None
        except KeyError as key_e:
            error_msg = f"Missing expected key in JSON response for {tekton_file_path}: {key_e}\nRaw Response: {response_content}"
            logger.error(error_msg)
            # Return error report and indicate failure for fixed yaml
            return f"Key Error: {error_msg}", None

    except Exception as e:
        error_msg = f"Error during Tekton pipeline validation for {tekton_file_path}: {e}"
        logger.error(error_msg, exc_info=True)
        # Indicate failure clearly
        return f"Validation Exception: {error_msg}", None


def process_jenkins_files(input_dir, output_dir, errors_log_path, run_number):
    """
    Process Jenkins files: convert to Tekton, validate/improve, save both versions, log reports.

    :param input_dir: Directory containing Jenkins pipeline files
    :param output_dir: Directory to save converted Tekton pipeline files
    :param errors_log_path: Path to log validation errors and reports
    :param run_number: The current execution run number
    """
    converter = JenkinsTektonConverter() # Assuming config is loaded within JenkinsTektonConverter

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    # Ensure errors log directory exists
    errors_log_dir = os.path.dirname(errors_log_path)
    if errors_log_dir:
        os.makedirs(errors_log_dir, exist_ok=True)

    # Clear or create the error log file at the start of processing for this run
    try:
        with open(errors_log_path, 'w') as log_file:
            log_file.write(f"# Tekton Validation Errors and Reports - Run {run_number}\n\n")
        logger.info(f"Initialized log file for Run {run_number}: {errors_log_path}")
    except IOError as e:
        logger.error(f"Failed to initialize log file {errors_log_path}: {e}")
        # Decide if we should exit or continue without logging
        return # Exit if log file cannot be initialized

    # Find Jenkins files
    patterns = ['*.jenkinsfile', '*.jenkins', '*.groovy']
    jenkins_files = []
    logger.info(f"Searching for Jenkins files in: {input_dir}")
    for pattern in patterns:
        found_files = glob.glob(os.path.join(input_dir, pattern))
        jenkins_files.extend(found_files)
        logger.info(f"Found {len(found_files)} files matching pattern {pattern}")

    if not jenkins_files:
        logger.warning("No Jenkins files found in the input directory.")
        return

    logger.info(f"Found total {len(jenkins_files)} Jenkins files to process.")

    for jenkins_file in jenkins_files:
        logger.info(f"--- Processing file: {jenkins_file} (Run: {run_number}) ---")
        base_filename = os.path.splitext(os.path.basename(jenkins_file))[0]
        # Construct filenames with run number
        json_output_path = os.path.join(output_dir, f"{run_number}-{base_filename}.json")
        initial_tekton_output_path = os.path.join(output_dir, f"{run_number}-{base_filename}-tekton-pipeline.yaml")
        validated_output_file_path = os.path.join(output_dir, f"{run_number}-validated-{base_filename}-tekton-pipeline.yaml")

        try:
            # Convert Jenkins file to JSON string
            logger.info(f"Converting {jenkins_file} to JSON...")
            json_content_str = converter.convert_jenkins_to_json(jenkins_file)
            if not json_content_str:
                logger.warning(f"Skipping file {jenkins_file} due to empty JSON conversion result.")
                continue

            # Save intermediate JSON
            logger.info(f"Saving intermediate JSON to {json_output_path}...")
            try:
                # Optionally validate JSON before saving (already done in convert_jenkins_to_json)
                # json.loads(json_content_str)
                with open(json_output_path, 'w') as json_file:
                    json_file.write(json_content_str)
                logger.info(f"Successfully saved intermediate JSON: {json_output_path}")
            except IOError as e:
                logger.error(f"Failed to save intermediate JSON {json_output_path}: {e}")
                continue # Skip to next file if we can't save JSON

            # Convert JSON content string to Tekton pipeline
            logger.info(f"Converting JSON to Tekton for {jenkins_file}...")
            tekton_content = converter.convert_json_to_tekton(json_content_str)
            if not tekton_content:
                logger.warning(f"Skipping Tekton conversion for {jenkins_file} due to empty Tekton content result.")
                continue

            # Save the initial Tekton pipeline file
            logger.info(f"Saving initial Tekton pipeline to {initial_tekton_output_path}...")
            try:
                with open(initial_tekton_output_path, 'w') as file:
                    file.write(tekton_content)
                logger.info(f"Successfully saved initial Tekton file: {initial_tekton_output_path}")
            except IOError as e:
                logger.error(f"Failed to save initial Tekton file {initial_tekton_output_path}: {e}")
                continue # Skip validation if saving failed

            # Validate the generated Tekton pipeline
            logger.info(f"Validating and improving Tekton pipeline {initial_tekton_output_path}...")
            validation_report, fixed_tekton_yaml = validate_tekton_pipeline(initial_tekton_output_path)

            # Log the validation report
            log_entry = f"--- Validation Report for Run {run_number}, File: {initial_tekton_output_path} ---\n"
            if validation_report:
                log_entry += validation_report + "\n"
            else:
                log_entry += f"Validation failed or no report generated. Check previous logs for errors related to {initial_tekton_output_path}.\n"
            log_entry += "--- End Report ---\n\n"

            # Append report to the central log file
            try:
                with open(errors_log_path, 'a') as log_file:
                    log_file.write(log_entry)
                logger.info(f"Validation report for {initial_tekton_output_path} appended to {errors_log_path}")
            except IOError as e:
                logger.error(f"Failed to append validation report to {errors_log_path}: {e}")

            # Save the validated/improved Tekton pipeline file if available
            if fixed_tekton_yaml and not fixed_tekton_yaml.startswith('# Fixed YAML missing'):
                logger.info(f"Saving validated/improved Tekton pipeline to {validated_output_file_path}...")
                try:
                    with open(validated_output_file_path, 'w') as file:
                        file.write(fixed_tekton_yaml)
                    logger.info(f"Successfully saved validated Tekton file: {validated_output_file_path}")

                    # --- Start Second Validation Step ---
                    logger.info(f"Starting second validation (fix focused) for {validated_output_file_path}...")
                    # Use the 'fix' prompt for the second pass
                    validation_report_2, fixed_tekton_yaml_2 = validate_tekton_pipeline(
                        validated_output_file_path,
                        prompt_file_basename="fix_tekton_pipeline.txt"
                    )

                    # Log the second validation report
                    log_entry_2 = f"--- Second Validation Report for Run {run_number}, File: {validated_output_file_path} ---\n"
                    if validation_report_2:
                        log_entry_2 += validation_report_2 + "\n"
                    else:
                        log_entry_2 += f"Second validation failed or no report generated. Check logs for {validated_output_file_path}.\n"
                    log_entry_2 += "--- End Second Report ---\n\n"
                    try:
                        with open(errors_log_path, 'a') as log_file:
                            log_file.write(log_entry_2)
                        logger.info(f"Second validation report for {validated_output_file_path} appended to {errors_log_path}")
                    except IOError as e:
                        logger.error(f"Failed to append second validation report to {errors_log_path}: {e}")

                    # Save the second validated/improved Tekton pipeline file if available
                    if fixed_tekton_yaml_2 and not fixed_tekton_yaml_2.startswith('# Fixed YAML missing'):
                        validated2_output_file_path = os.path.join(output_dir, f"{run_number}-validated2-{base_filename}-tekton-pipeline.yaml")
                        logger.info(f"Saving second validated/improved Tekton pipeline to {validated2_output_file_path}...")
                        try:
                            with open(validated2_output_file_path, 'w') as file:
                                file.write(fixed_tekton_yaml_2)
                            logger.info(f"Successfully saved second validated Tekton file: {validated2_output_file_path}")
                        except IOError as e:
                            logger.error(f"Failed to save second validated Tekton file {validated2_output_file_path}: {e}")
                    else:
                        logger.warning(f"No valid fixed Tekton YAML provided from second validation for {validated_output_file_path}. Skipping save for validated2 file.")
                    # --- End Second Validation Step ---

                except IOError as e:
                    logger.error(f"Failed to save validated Tekton file {validated_output_file_path}: {e}")
            else:
                logger.warning(f"No valid fixed Tekton YAML provided or validation failed for {initial_tekton_output_path}. Skipping save for validated file and subsequent second validation.")

        except Exception as e:
            logger.error(f"An unexpected error occurred processing file {jenkins_file}: {e}", exc_info=True)

        logger.info(f"--- Finished processing file: {jenkins_file} ---")

    logger.info("Conversion and validation process finished.")

def get_and_increment_run_number(counter_file):
    """Reads the run number from a file, increments it, saves it back, and returns the NEW run number."""
    run_number = 1 # Default if file doesn't exist or is invalid
    try:
        if os.path.exists(counter_file):
            with open(counter_file, 'r') as f:
                try:
                    current_number = int(f.read().strip())
                    run_number = current_number + 1
                except ValueError:
                    logger.warning(f"Invalid content in {counter_file}. Resetting run number to 1.")
                    run_number = 1
        else:
             logger.info(f"Counter file {counter_file} not found. Starting run number from 1.")
             run_number = 1 # Start from 1 if file does not exist
    except IOError as e:
        logger.error(f"Could not read counter file {counter_file}: {e}. Starting run number from 1.")
        run_number = 1

    try:
        with open(counter_file, 'w') as f:
            f.write(str(run_number))
        logger.info(f"Current run number: {run_number}. Updated counter file: {counter_file}")
    except IOError as e:
        # If writing fails, we still proceed with the potentially correct run number, but log the error.
        logger.error(f"Could not write to counter file {counter_file}: {e}. Proceeding with run number {run_number}.")

    return run_number

def main():
    # Initialize converter to load configuration
    try:
        converter = JenkinsTektonConverter()
        config = converter.config
    except Exception as config_e:
        logger.error(f"Failed to load configuration: {config_e}")
        print(f"Error: Failed to load configuration. Check config.yaml and .env. Details: {config_e}")
        return # Exit if config fails

    # Get and increment run number
    run_number = get_and_increment_run_number('run_counter.txt')

    # Use directories and log path from configuration, constructing absolute paths
    base_dir = os.path.dirname(os.path.dirname(__file__)) # Project root
    input_dir = os.path.join(base_dir, config['conversion']['input_directory'])
    output_dir = os.path.join(base_dir, config['conversion']['output_directory'])
    # Define error log path relative to project root
    errors_log_path = os.path.join(base_dir, 'tekton_validation_errors.log')

    print(f"Starting Jenkins to Tekton conversion...")
    print(f"Input directory: {input_dir}")
    print(f"Output directory: {output_dir}")
    print(f"Validation Log: {errors_log_path}")

    # Configure root logger based on config file (if converter didn't already)
    log_file = config['logging'].get('file')
    log_level_str = config['logging'].get('level', 'INFO').upper()
    log_level = getattr(logging, log_level_str, logging.INFO)
    log_format = '%(asctime)s - %(levelname)s - %(message)s'

    # Remove existing handlers and configure
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
    logging.basicConfig(level=log_level, format=log_format, filename=log_file)
    # Add console handler too, respecting the level
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(logging.Formatter(log_format))
    logging.getLogger('').addHandler(console_handler)

    # Process Jenkins files (conversion, validation, saving fixed files, logging reports)
    process_jenkins_files(input_dir, output_dir, errors_log_path, run_number)
    print("\nConversion and validation process finished.")

    # --- Argument Parsing ---
    parser = argparse.ArgumentParser(description="Convert Jenkinsfiles to Tekton Pipelines and optionally refine prompts.")
    parser.add_argument("--refine-prompt", action="store_true", help="If set, attempts to refine the json2tekton prompt based on validation feedback.")
    args = parser.parse_args()

    # --- Attempt to Refine Prompt based on logs (ONLY IF FLAG IS SET) ---
    if args.refine_prompt:
        print("\n--refine-prompt flag detected.")
        print("Attempting to refine the json2tekton prompt based on the latest validation feedback...")
        prompts_dir = os.path.join(os.path.dirname(__file__), 'prompts')
        json2tekton_prompt_path = os.path.join(prompts_dir, 'json2tekton.txt')
        refinement_success = refine_json2tekton_prompt(errors_log_path, json2tekton_prompt_path)
        if refinement_success:
            print(f"Prompt refinement successful. The updated prompt is now in {json2tekton_prompt_path}.")
        else:
            print("Prompt refinement failed. Check logs for details.")
    else:
        print("\nSkipping prompt refinement step (--refine-prompt flag not provided).")

    # Check if the validation log file has significant content (more than header)
    try:
        with open(errors_log_path, 'r') as errors_log:
            # Simple check if file contains more than just the initial header line(s)
            errors_content = errors_log.read().strip()
            # Check if there are lines indicating actual reports or errors
            if len(errors_content.splitlines()) > 2: # Adjust threshold as needed
                 print(f"\nValidation reports and potentially errors/warnings were logged.")
                 print(f"Please review the log file for details: {errors_log_path}")
            else:
                 print("\nNo significant validation issues logged.")
    except FileNotFoundError:
        print(f"\nValidation log file not found at: {errors_log_path}")
    except Exception as log_read_e:
        print(f"\nError reading validation log file {errors_log_path}: {log_read_e}")

if __name__ == "__main__":
    main()
