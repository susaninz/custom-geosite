#!/usr/bin/env python3
"""
Build sing-box rule-set source JSON files from domain-list-community data.

Parses domain-list-community text format and generates sing-box rule-set
JSON source files (version 2) for compilation with `sing-box rule-set compile`.

Usage:
    python3 build_srs.py --data-dir domain-list-community/data --output-dir build/srs \
        youtube instagram facebook "category-ai-!cn:ai"

Category format: category_name[:output_name]
  - category_name: name of the data file in domain-list-community
  - output_name (optional): base name for output file (default: same as category_name)
  - Example: "category-ai-!cn:ai" reads category-ai-!cn, outputs geosite-ai.json
"""

import argparse
import json
import os
import sys


def parse_data_file(data_dir, category, exclude_attrs=None, visited=None):
    """Parse a domain-list-community data file, resolving includes recursively.

    Handles:
      - Plain entries (domain suffix): youtube.com
      - full: entries (exact domain): full:api.example.com
      - keyword: entries: keyword:youtube
      - include: directives: include:other-category
      - @attr annotations: domain.com @ads @cn
      - !attr in category name: category-ai-!cn excludes @cn entries
      - regexp: entries are SKIPPED (not supported in sing-box rule-set)

    Returns (suffixes, domains, keywords) lists.
    """
    if visited is None:
        visited = set()
    if exclude_attrs is None:
        exclude_attrs = set()

    if category in visited:
        return [], [], []
    visited.add(category)

    # Try exact filename first (e.g. "category-ai-!cn" exists as a file)
    filepath = os.path.join(data_dir, category)

    # If not found and has -!attr, try base file with attribute exclusion
    if not os.path.exists(filepath) and '-!' in category:
        base, attr = category.rsplit('-!', 1)
        exclude_attrs = exclude_attrs | {attr}
        filepath = os.path.join(data_dir, base)

    if not os.path.exists(filepath):
        print(f"  WARNING: {category} not found, skipping", file=sys.stderr)
        return [], [], []

    suffixes = []
    domains = []
    keywords = []

    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            # Split entry from attributes and comments
            parts = line.split()
            entry = parts[0]
            attrs = set()
            for p in parts[1:]:
                if p.startswith('#'):
                    break
                if p.startswith('@'):
                    attrs.add(p[1:])

            # Skip entries with excluded attributes
            if exclude_attrs & attrs:
                continue

            if entry.startswith('include:'):
                sub_category = entry[8:]
                s, d, k = parse_data_file(data_dir, sub_category, exclude_attrs, visited)
                suffixes.extend(s)
                domains.extend(d)
                keywords.extend(k)
            elif entry.startswith('full:'):
                domains.append(entry[5:])
            elif entry.startswith('keyword:'):
                keywords.append(entry[8:])
            elif entry.startswith('regexp:'):
                pass  # sing-box rule-set doesn't support regex
            else:
                suffixes.append(entry)

    return suffixes, domains, keywords


def build_ruleset_json(suffixes, domains, keywords):
    """Build sing-box rule-set source JSON (version 2)."""
    rule = {}
    unique_domains = sorted(set(domains))
    unique_suffixes = sorted(set(suffixes))
    unique_keywords = sorted(set(keywords))

    if unique_domains:
        rule['domain'] = unique_domains
    if unique_suffixes:
        rule['domain_suffix'] = unique_suffixes
    if unique_keywords:
        rule['domain_keyword'] = unique_keywords

    return {
        'version': 2,
        'rules': [rule] if rule else []
    }


def main():
    parser = argparse.ArgumentParser(
        description='Build sing-box .srs source JSON from domain-list-community data'
    )
    parser.add_argument('--data-dir', required=True,
                        help='Path to domain-list-community/data directory')
    parser.add_argument('--output-dir', required=True,
                        help='Output directory for JSON source files')
    parser.add_argument('categories', nargs='+',
                        help='Categories to process (format: name[:output_name])')
    args = parser.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)

    total_entries = 0

    for spec in args.categories:
        if ':' in spec:
            category, output_name = spec.split(':', 1)
        else:
            category = output_name = spec

        suffixes, domains, keywords = parse_data_file(args.data_dir, category)
        ruleset = build_ruleset_json(suffixes, domains, keywords)

        n_suffix = len(ruleset['rules'][0].get('domain_suffix', [])) if ruleset['rules'] else 0
        n_domain = len(ruleset['rules'][0].get('domain', [])) if ruleset['rules'] else 0
        n_keyword = len(ruleset['rules'][0].get('domain_keyword', [])) if ruleset['rules'] else 0
        n_total = n_suffix + n_domain + n_keyword
        total_entries += n_total

        outfile = os.path.join(args.output_dir, f'geosite-{output_name}.json')
        with open(outfile, 'w') as f:
            json.dump(ruleset, f, indent=2, ensure_ascii=False)
            f.write('\n')

        print(f'  {category} -> geosite-{output_name}.json: '
              f'{n_total} entries ({n_suffix} suffix, {n_domain} domain, {n_keyword} keyword)')

    print(f'\nDone: {len(args.categories)} rule-sets, {total_entries} total entries')


if __name__ == '__main__':
    main()
