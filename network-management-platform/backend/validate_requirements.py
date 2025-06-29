#!/usr/bin/env python3
"""Validate requirements.txt syntax and check for issues"""

import re

def validate_requirements():
    errors = []
    warnings = []
    
    with open('requirements.txt', 'r') as f:
        lines = f.readlines()
    
    for i, line in enumerate(lines, 1):
        line = line.strip()
        
        # Skip empty lines and comments
        if not line or line.startswith('#'):
            continue
            
        # Check for valid package specification
        if '==' in line:
            parts = line.split('==')
            if len(parts) != 2:
                errors.append(f"Line {i}: Invalid version specification: {line}")
            else:
                package, version = parts
                if '[' in package:
                    # Check extras syntax
                    if not re.match(r'^[\w\-]+\[[\w,]+\]$', package):
                        errors.append(f"Line {i}: Invalid extras syntax: {package}")
                        
        elif '>=' in line or '<=' in line or '>' in line or '<' in line:
            # Version ranges
            if not re.match(r'^[\w\-\[\]]+[><=]+[\d\.]+.*$', line):
                errors.append(f"Line {i}: Invalid version range: {line}")
        else:
            # No version specified
            warnings.append(f"Line {i}: No version specified for {line}")
    
    return errors, warnings

if __name__ == "__main__":
    errors, warnings = validate_requirements()
    
    if errors:
        print("❌ Errors found:")
        for error in errors:
            print(f"  - {error}")
    
    if warnings:
        print("\n⚠️  Warnings:")
        for warning in warnings:
            print(f"  - {warning}")
    
    if not errors and not warnings:
        print("✅ requirements.txt is valid!")
    
    exit(1 if errors else 0)