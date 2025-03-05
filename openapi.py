import os

import prance
import yaml
from prance.util.url import ResolutionError


class OpenAPIParser:
    def __init__(self, yaml_path, strict=False):
        """
        Initialize the OpenAPI parser

        Args:
            yaml_path (str): Path to the OpenAPI YAML file
            strict (bool): Whether to use strict validation
        """
        self.yaml_path = yaml_path
        self.strict = strict
        self.spec = None
        self.resolved_spec = None

    def parse(self):
        """Parse the OpenAPI file with reference resolution"""
        try:
            # Make sure we're working from the directory containing the YAML file
            yaml_dir = os.path.dirname(os.path.abspath(self.yaml_path))
            yaml_file = os.path.basename(self.yaml_path)

            # Store the current working directory
            original_dir = os.getcwd()

            try:
                # Change to the directory containing the YAML file
                os.chdir(yaml_dir)

                # First, load the raw YAML to preserve original structure
                with open(yaml_file, "r", encoding="utf-8") as f:
                    self.spec = yaml.safe_load(f)

                # Then use prance to resolve references
                parser = prance.ResolvingParser(
                    yaml_file, strict=self.strict, backend="openapi-spec-validator"
                )
                self.resolved_spec = parser.specification
            finally:
                # Restore the original working directory
                os.chdir(original_dir)

            return True

        except ResolutionError as e:
            print(f"Reference resolution error: {e}")
            return False
        except Exception as e:
            print(f"Error parsing OpenAPI file: {e}")
            return False

    def get_resolved_spec(self):
        """Get the spec with all references resolved"""
        return self.resolved_spec
