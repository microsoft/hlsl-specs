#!/usr/bin/env python3
"""
Script to update Jekyll front matter for HLSL proposal markdown files.

This script processes .md files in the proposals directory and:
1. Extracts metadata from bullet points (Proposal, Author, Sponsor, Status, Planned Version)
2. Adds Jekyll front matter if it doesn't exist
3. By default, preserves existing front matter values (warns about conflicts)
4. With --overwrite flag, replaces existing front matter with extracted values
5. Skips the templates subdirectory
"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple


def extract_title_from_heading(content: str) -> Optional[str]:
    """Extract the first H1 heading as the title."""
    lines = content.split('\n')
    for line in lines:
        line = line.strip()
        if line.startswith('# '):
            return line[2:].strip()
    return None


def extract_metadata_from_content(content: str) -> Dict[str, str]:
    """Extract metadata from bullet point format in the content."""
    metadata = {}
    
    # Simple patterns to match the start of bullet points
    simple_patterns = {
        'proposal': r'^\*\s*Proposal:\s*\[([^\]]+)\]',
        'author': r'^\*\s*Author\(s\):\s*(.+)$',
        'sponsor': r'^\*\s*Sponsor:\s*(.+)$', 
        'status': r'^\*\s*Status:\s*(.+)$',
        'planned_version': r'^\*\s*Planned\s+Version:\s*(.+)$'
    }
    
    lines = content.split('\n')
    current_field = None
    current_value = ""
    
    def save_current_field():
        """Helper to save the current field if it exists."""
        if current_field and current_value:
            # Clean up the value
            value = current_value.strip()
            if current_field == 'author' or current_field == 'sponsor':
                # Remove markdown links: [Name](url) -> Name
                value = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', value)
                # Clean up any remaining formatting
                value = re.sub(r'\s+', ' ', value)  # normalize whitespace
            elif current_field == 'status':
                # Remove markdown formatting like **text** -> text
                value = re.sub(r'\*\*([^*]+)\*\*', r'\1', value)
            
            metadata[current_field] = value
    
    i = 0
    while i < len(lines):
        line = lines[i]
        line_stripped = line.strip()
        
        # Check if this is a new bullet point
        found_match = False
        for key, pattern in simple_patterns.items():
            match = re.match(pattern, line_stripped, re.IGNORECASE)
            if match:
                # Save previous field if any
                save_current_field()
                
                # Start new field
                current_field = key
                current_value = match.group(1).strip()
                found_match = True
                
                # For multi-line fields, look ahead to see if next lines are continuations
                j = i + 1
                while j < len(lines):
                    next_line = lines[j]
                    next_line_stripped = next_line.strip()
                    
                    # Stop if we hit an empty line
                    if not next_line_stripped:
                        break
                        
                    # Stop if we hit a new section (starts with ##)
                    if next_line_stripped.startswith('##'):
                        break
                        
                    # Stop if we hit another bullet point
                    if any(re.match(p, next_line_stripped, re.IGNORECASE) for p in simple_patterns.values()):
                        break
                        
                    # Check if this line continues the current field (indented continuation)
                    if next_line.startswith('    ') and next_line_stripped:
                        current_value += " " + next_line_stripped
                        j += 1
                    else:
                        # Not a continuation, stop here
                        break
                
                # Skip the lines we've already processed
                i = j - 1
                break
        
        if not found_match:
            # If we're not in a field and this line starts a new section, we're done with metadata
            if not current_field and line_stripped.startswith('##'):
                break
        
        i += 1
    
    # Don't forget the last field
    save_current_field()
    
    return metadata


def has_front_matter(content: str) -> bool:
    """Check if the file already has Jekyll front matter."""
    return content.strip().startswith('---')


def parse_simple_yaml(yaml_content: str) -> Dict[str, str]:
    """Simple YAML parser for basic key: value pairs."""
    result = {}
    for line in yaml_content.split('\n'):
        line = line.strip()
        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip()
            # Remove quotes if present and handle escaped quotes
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1].replace('\\"', '"')
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1].replace("\\'", "'")
            result[key] = value
    return result


def parse_existing_front_matter(content: str) -> Tuple[Dict[str, str], str]:
    """Parse existing front matter and return (front_matter_dict, remaining_content)."""
    if not has_front_matter(content):
        return {}, content
    
    lines = content.split('\n')
    if lines[0].strip() != '---':
        return {}, content
    
    front_matter_lines = []
    content_start = 1
    
    for i in range(1, len(lines)):
        if lines[i].strip() == '---':
            content_start = i + 1
            break
        front_matter_lines.append(lines[i])
    
    # Parse the YAML front matter
    front_matter_yaml = '\n'.join(front_matter_lines)
    front_matter_dict = {}
    
    try:
        if front_matter_yaml.strip():
            front_matter_dict = parse_simple_yaml(front_matter_yaml)
    except Exception as e:
        print(f"Warning: Could not parse existing front matter: {e}", file=sys.stderr)
        front_matter_dict = {}
    
    remaining_content = '\n'.join(lines[content_start:])
    return front_matter_dict, remaining_content


def create_front_matter(metadata: Dict[str, str], title: Optional[str], existing_front_matter: Dict[str, str] = None, overwrite: bool = False) -> str:
    """Create Jekyll front matter from extracted metadata, merging with existing front matter."""
    if existing_front_matter is None:
        existing_front_matter = {}
    
    # Start with existing front matter, then add/override with extracted metadata
    merged_front_matter = existing_front_matter.copy()
    
    # Add extracted values based on overwrite mode
    if title:
        if overwrite or 'title' not in merged_front_matter:
            merged_front_matter['title'] = title
    
    for key in ['proposal', 'author', 'sponsor', 'status', 'planned_version']:
        if key in metadata:
            if overwrite or key not in merged_front_matter:
                merged_front_matter[key] = metadata[key]
    
    # Convert to YAML format
    front_matter_lines = ['---']
    
    # Preserve order: existing keys first, then new ones
    all_keys = list(existing_front_matter.keys())
    for key in ['title', 'proposal', 'author', 'sponsor', 'status', 'planned_version']:
        if key in merged_front_matter and key not in all_keys:
            all_keys.append(key)
    
    for key in all_keys:
        if key in merged_front_matter:
            value = merged_front_matter[key]
            # Ensure proper YAML quoting for string values
            if isinstance(value, str):
                # Escape quotes and use proper YAML quoting
                escaped_value = value.replace('"', '\\"')
                front_matter_lines.append(f'{key}: "{escaped_value}"')
            else:
                front_matter_lines.append(f'{key}: {value}')
    
    front_matter_lines.append('---')
    
    return '\n'.join(front_matter_lines)


def process_file(file_path: Path, overwrite: bool = False) -> bool:
    """Process a single markdown file. Returns True if file was modified."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading {file_path}: {e}", file=sys.stderr)
        return False
    
    # Extract metadata from content
    metadata = extract_metadata_from_content(content)
    title = extract_title_from_heading(content)
    
    # Parse existing front matter
    existing_front_matter, content_without_front_matter = parse_existing_front_matter(content)
    
    # Check if we have anything to add
    has_existing_front_matter = bool(existing_front_matter)
    has_new_metadata = bool(metadata or title)
    
    if not has_new_metadata and not has_existing_front_matter:
        return False
    
    # Check for conflicts between existing front matter and extracted values
    conflicts = []
    if title and 'title' in existing_front_matter and existing_front_matter['title'] != title:
        conflicts.append(f"title: existing='{existing_front_matter['title']}' vs extracted='{title}'")
    
    for key in ['proposal', 'author', 'sponsor', 'status', 'planned_version']:
        if key in metadata and key in existing_front_matter and existing_front_matter[key] != metadata[key]:
            conflicts.append(f"{key}: existing='{existing_front_matter[key]}' vs extracted='{metadata[key]}'")
    
    # Log conflicts (and what will happen)
    for conflict in conflicts:
        if overwrite:
            print(f"Info: {file_path} - overwriting conflicting metadata - {conflict}", file=sys.stderr)
        else:
            print(f"Warning: {file_path} has conflicting metadata - {conflict}", file=sys.stderr)
    
    # Check if we need to add any new fields or overwrite existing ones
    needs_update = False
    added_fields = []
    
    if overwrite:
        # In overwrite mode, update if we have any metadata to write
        if title or metadata:
            needs_update = True
            if title:
                added_fields.append('title')
            for key in ['proposal', 'author', 'sponsor', 'status', 'planned_version']:
                if key in metadata:
                    added_fields.append(key)
    else:
        # In normal mode, only add fields that don't exist
        if title and 'title' not in existing_front_matter:
            needs_update = True
            added_fields.append('title')
        
        for key in ['proposal', 'author', 'sponsor', 'status', 'planned_version']:
            if key in metadata and key not in existing_front_matter:
                needs_update = True
                added_fields.append(key)
    
    if has_existing_front_matter and not needs_update:
        return False
    
    # Create merged front matter
    front_matter = create_front_matter(metadata, title, existing_front_matter, overwrite)
    
    # Combine front matter with content (without existing front matter)
    new_content = front_matter + '\n' + content_without_front_matter
    
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return True
    except Exception as e:
        print(f"Error writing {file_path}: {e}", file=sys.stderr)
        return False


def main():
    """Main function to process all proposal markdown files."""
    parser = argparse.ArgumentParser(description="Update Jekyll front matter for HLSL proposal markdown files")
    parser.add_argument('--overwrite', action='store_true', 
                       help="Overwrite existing front matter values with extracted metadata (default: only add missing fields)")
    
    args = parser.parse_args()
    
    # Get the script directory and find the proposals directory
    script_dir = Path(__file__).parent
    repo_root = script_dir.parent
    proposals_dir = repo_root / 'proposals'
    
    if not proposals_dir.exists():
        print(f"Error: Proposals directory not found at {proposals_dir}", file=sys.stderr)
        sys.exit(1)
    
    # Find all .md files in proposals directory and subdirectories
    md_files = []
    for file_path in proposals_dir.rglob('*.md'):
        # Skip files in templates subdirectory
        if 'templates' in file_path.parts:
            continue
        
        # Skip index.md and other non-proposal files
        if file_path.name in ['index.md', 'README.md']:
            continue
            
        md_files.append(file_path)
    
    if not md_files:
        print("No proposal markdown files found to process")
        return
    
    modified_count = 0
    for file_path in sorted(md_files):
        if process_file(file_path, args.overwrite):
            modified_count += 1
    
    if modified_count > 0:
        print(f"Updated front matter for {modified_count} files")
    else:
        print("No files needed front matter updates")


if __name__ == '__main__':
    main()
