#!/usr/bin/env python3
"""
Plot Quarkus native performance metrics across different configurations.
"""

import json
import os
import glob
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path

# Set style
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (14, 10)

def extract_config_name(folder_path):
    """Extract configuration name from folder path by removing common prefix."""
    folder_name = os.path.basename(folder_path)
    return folder_name

def detect_common_prefix(folder_names):
    """Detect the common prefix from a list of folder names."""
    if not folder_names:
        return ""
    
    if len(folder_names) == 1:
        # If only one folder, try to find a reasonable split point
        name = folder_names[0]
        # Look for the last hyphen before a descriptive part
        parts = name.split('-')
        if len(parts) > 1:
            # Keep everything up to and including the last version-like part
            for i in range(len(parts) - 1, -1, -1):
                if any(char.isdigit() for char in parts[i]):
                    return '-'.join(parts[:i+1]) + '-'
        return ""
    
    # Find common prefix among all folder names
    prefix = folder_names[0]
    for name in folder_names[1:]:
        # Find common prefix between current prefix and this name
        common = ""
        for i, (c1, c2) in enumerate(zip(prefix, name)):
            if c1 == c2:
                common += c1
            else:
                break
        prefix = common
    
    # Trim to last complete word (ending with hyphen)
    if '-' in prefix:
        prefix = prefix[:prefix.rfind('-') + 1]
    
    return prefix

def load_metrics():
    """Load all metrics.json files from subdirectories."""
    data = []
    
    # Find all metrics.json files
    metrics_files = glob.glob("*/target-host/metrics.json")
    
    # First pass: collect all folder names
    folders = []
    for metrics_file in metrics_files:
        folder = os.path.dirname(os.path.dirname(metrics_file))
        folders.append(folder)
    
    # Detect common prefix
    folder_names = [os.path.basename(f) for f in folders]
    common_prefix = detect_common_prefix(folder_names)
    
    # Second pass: load metrics with cleaned config names
    for metrics_file in metrics_files:
        folder = os.path.dirname(os.path.dirname(metrics_file))
        folder_name = os.path.basename(folder)
        
        # Remove common prefix
        if common_prefix and folder_name.startswith(common_prefix):
            config = folder_name[len(common_prefix):]
        else:
            config = folder_name
        
        with open(metrics_file, 'r') as f:
            metrics = json.load(f)
        
        if 'results' in metrics and 'quarkus3-native' in metrics['results']:
            result = metrics['results']['quarkus3-native']
            data.append({
                'config': config,
                'metrics': result
            })
    
    return data

def prepare_dataframe(data, metric_path, metric_name):
    """
    Prepare a dataframe for plotting from nested metric data.
    
    Args:
        data: List of configuration data dictionaries
        metric_path: Path to navigate through nested metrics structure
        metric_name: Name for the metric column in the dataframe
    """
    rows = []
    
    for item in data:
        config = item['config']
        metrics = item['metrics']
        
        # Navigate through nested structure
        current = metrics
        for key in metric_path:
            if key in current:
                current = current[key]
            else:
                current = None
                break
        
        if current is not None and isinstance(current, list):
            for value in current:
                rows.append({
                    'Configuration': config,
                    metric_name: value
                })
    
    return pd.DataFrame(rows)

def get_config_order_by_startup_rss(data):
    """
    Determine configuration order based on average startup RSS.
    Special rules:
    - 'none' configuration always comes first (baseline)
    - 'all' configuration always comes last
    - Other configurations sorted by startup RSS (lower memory first)
    """
    config_rss = {}
    none_config = None
    all_config = None
    
    for item in data:
        config = item['config']
        metrics = item['metrics']
        
        # Track special configurations
        if config == 'none':
            none_config = config
        elif config == 'all':
            all_config = config
        
        # Get startup RSS values
        if 'rss' in metrics and 'startup' in metrics['rss']:
            startup_rss = metrics['rss']['startup']
            if isinstance(startup_rss, list) and startup_rss:
                config_rss[config] = np.mean(startup_rss)
    
    # Sort middle configurations by RSS (ascending - lower memory first)
    middle_configs = sorted(
        [(c, rss) for c, rss in config_rss.items() if c not in ['none', 'all']],
        key=lambda x: x[1]
    )
    
    # Build final order: none first, then sorted by RSS, then all last
    result = []
    if none_config:
        result.append(none_config)
    result.extend([config for config, _ in middle_configs])
    if all_config:
        result.append(all_config)
    
    return result

def plot_swarmplot(df, metric_name, title, ylabel, filename, config_order=None):
    """Create a swarm plot with min and max indicators for the given metric."""
    plt.figure(figsize=(10, 8))
    
    # Use provided order or sort alphabetically
    if config_order is None:
        config_order = sorted(df['Configuration'].unique())
    else:
        # Filter to only configs present in this dataframe
        config_order = [c for c in config_order if c in df['Configuration'].unique()]
    
    # Create swarm plot
    palette = sns.color_palette('Set2')
    ax = sns.violinplot(data=df, x='Configuration', y=metric_name, order=config_order,
                     legend=False, inner='quart', color=palette[2], linewidth=2, edgecolor='white')
    ax = sns.swarmplot(data=df, x='Configuration', y=metric_name, order=config_order,
                     legend=False, color=palette[1], linewidth=0.5)
    
    # # Add min and max points
    # for i, config in enumerate(config_order):
    #     config_data = df[df['Configuration'] == config][metric_name]
    #     if len(config_data) > 0:
    #         min_val = config_data.min()
    #         max_val = config_data.max()
            
    #         # Plot min as a downward triangle
    #         ax.plot(i, min_val, marker='v', color='blue', markersize=10,
    #                markeredgecolor='darkblue', markeredgewidth=1.5, zorder=3,
    #                label='Min' if i == 0 else '')
            
    #         # Plot max as an upward triangle
    #         ax.plot(i, max_val, marker='^', color='red', markersize=10,
    #                markeredgecolor='darkred', markeredgewidth=1.5, zorder=3,
    #                label='Max' if i == 0 else '')
    
    # # Add legend for min and max indicators
    # handles, labels = ax.get_legend_handles_labels()
    # if handles:
    #     ax.legend(handles[:2], labels[:2], loc='upper right', fontsize=10)
    
    plt.title(title, fontsize=16, fontweight='bold')
    plt.xlabel('Configuration', fontsize=12)
    plt.ylabel(ylabel, fontsize=12)
    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved: {filename}")

def plot_bar_with_error(data, metric_path, metric_name, title, ylabel, filename):
    """Create a bar plot with error bars."""
    stats = []
    
    for item in data:
        config = item['config']
        metrics = item['metrics']
        
        # Navigate through nested structure
        current = metrics
        for key in metric_path:
            if key in current:
                current = current[key]
            else:
                current = None
                break
        
        if current is not None and isinstance(current, list):
            values = current
            
            stats.append({
                'Configuration': config,
                'Mean': np.mean(values),
                'Std': np.std(values)
            })
    
    df = pd.DataFrame(stats)
    df = df.sort_values('Configuration')
    
    plt.figure(figsize=(14, 8))
    ax = plt.bar(range(len(df)), df['Mean'], yerr=df['Std'], 
                 capsize=5, alpha=0.7, color='steelblue', edgecolor='black')
    
    plt.xticks(range(len(df)), df['Configuration'], rotation=45, ha='right')
    plt.title(title, fontsize=16, fontweight='bold')
    plt.xlabel('Configuration', fontsize=12)
    plt.ylabel(ylabel, fontsize=12)
    plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()
    plt.savefig(filename, dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved: {filename}")

def plot_summary_comparison(data, config_order=None):
    """Create a comprehensive comparison plot."""
    metrics_to_compare = [
        ('avBuildTime', 'Build Time (s)'),
        ('avStartTime', 'Startup Time (ms)'),
        ('avThroughput', 'Throughput (req/s)'),
        ('avMaxRss', 'Max RSS (MB)'),
    ]
    
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    axes = axes.flatten()
    
    for idx, (metric_key, metric_label) in enumerate(metrics_to_compare):
        ax = axes[idx]
        
        config_values = {}
        
        for item in data:
            config = item['config']
            metrics = item['metrics']
            
            # Find the metric in different locations
            value = None
            if metric_key in metrics.get('build', {}):
                value = metrics['build'][metric_key]
            elif metric_key in metrics.get('startup', {}):
                value = metrics['startup'][metric_key]
            elif metric_key in metrics.get('load', {}):
                value = metrics['load'][metric_key]
            
            if value is not None:
                config_values[config] = value
        
        # Use provided order or sort by configuration name
        if config_order:
            configs = [c for c in config_order if c in config_values]
        else:
            configs = sorted(config_values.keys())
        
        values = [config_values[c] for c in configs]
        
        ax.bar(range(len(configs)), values, alpha=0.7, color='steelblue', edgecolor='black')
        ax.set_xticks(range(len(configs)))
        ax.set_xticklabels(configs, rotation=45, ha='right', fontsize=9)
        ax.set_title(metric_label, fontsize=12, fontweight='bold')
        ax.grid(axis='y', alpha=0.3)
    
    plt.suptitle('Performance Metrics Comparison Across Configurations', 
                 fontsize=16, fontweight='bold', y=1.00)
    plt.tight_layout()
    plt.savefig('summary_comparison.png', dpi=300, bbox_inches='tight')
    plt.close()
    print(f"Saved: summary_comparison.png")

def main():
    """Main function to generate all plots."""
    print("Loading metrics data...")
    
    # Find all metrics.json files to detect common prefix
    metrics_files = glob.glob("*/target-host/metrics.json")
    folders = [os.path.dirname(os.path.dirname(f)) for f in metrics_files]
    folder_names = [os.path.basename(f) for f in folders]
    common_prefix = detect_common_prefix(folder_names)
    
    if common_prefix:
        print(f"Detected common prefix: '{common_prefix}'")
        print(f"Configuration names will have this prefix removed.\n")
    
    data = load_metrics()
    
    if not data:
        print("No metrics.json files found!")
        return
    
    print(f"Found {len(data)} configurations:")
    for item in data:
        print(f"  - {item['config']}")
    
    # Determine configuration order based on startup RSS
    config_order = get_config_order_by_startup_rss(data)
    print(f"\nConfiguration order (by startup RSS, lowest first):")
    for i, config in enumerate(config_order, 1):
        print(f"  {i}. {config}")
    
    print("\nGenerating plots...")
    
    # Create output directory
    os.makedirs('plots', exist_ok=True)
    os.chdir('plots')
    
    # 1. Build Times (box plot)
    df_build = prepare_dataframe(data, ['build', 'timings'], 'Build Time (s)')
    if not df_build.empty:
        plot_swarmplot(df_build, 'Build Time (s)',
                   'Native Image Build Times Across Configurations',
                   'Build Time (seconds)', 'build_times.png', config_order)
    
    # 2. Startup Times (box plot)
    df_startup = prepare_dataframe(data, ['startup', 'timings'], 'Startup Time (ms)')
    print(df_startup)
    if not df_startup.empty:
        plot_swarmplot(df_startup, 'Startup Time (ms)',
                   'Application Startup Times Across Configurations',
                   'Startup Time (milliseconds)', 'startup_times.png', config_order)
    
    # 3. Native Build RSS (box plot)
    df_native_rss = prepare_dataframe(data, ['build', 'native', 'rss'], 'Native Build RSS (GB)')
    if not df_native_rss.empty:
        plot_swarmplot(df_native_rss, 'Native Build RSS (GB)',
                   'Native Image Build Memory Usage',
                   'RSS Memory (GB)', 'native_build_rss.png', config_order)
    
    # 4. Startup RSS (box plot)
    df_startup_rss = prepare_dataframe(data, ['rss', 'startup'], 'Startup RSS (MB)')
    if not df_startup_rss.empty:
        plot_swarmplot(df_startup_rss, 'Startup RSS (MB)',
                   'Application Startup Memory Usage',
                   'RSS Memory (MB)', 'startup_rss.png', config_order)
    
    # 5. First Request RSS (box plot)
    df_first_req_rss = prepare_dataframe(data, ['rss', 'firstRequest'], 'First Request RSS (MB)')
    if not df_first_req_rss.empty:
        plot_swarmplot(df_first_req_rss, 'First Request RSS (MB)',
                   'Memory Usage at First Request',
                   'RSS Memory (MB)', 'first_request_rss.png', config_order)
    
    # 6. Load Test Throughput (box plot)
    df_throughput = prepare_dataframe(data, ['load', 'throughput'], 'Throughput (req/s)')
    if not df_throughput.empty:
        plot_swarmplot(df_throughput, 'Throughput (req/s)',
                   'Load Test Throughput Across Configurations',
                   'Throughput (requests/second)', 'throughput.png', config_order)
    
    # 7. Load Test Max RSS (box plot)
    df_load_rss = prepare_dataframe(data, ['load', 'rss'], 'Load Test RSS (MB)')
    if not df_load_rss.empty:
        plot_swarmplot(df_load_rss, 'Load Test RSS (MB)',
                   'Memory Usage During Load Test',
                   'RSS Memory (MB)', 'load_test_rss.png', config_order)
    
    # 8. Throughput Density (box plot)
    df_density = prepare_dataframe(data, ['load', 'throughputDensity'], 'Throughput Density')
    if not df_density.empty:
        plot_swarmplot(df_density, 'Throughput Density',
                   'Throughput Density (Throughput per MB RSS)',
                   'Throughput Density (req/s per MB)', 'throughput_density.png', config_order)
    
    # 9. Summary comparison
    plot_summary_comparison(data, config_order)
    
    # 10. Generate statistics table (using all data points)
    print("\nGenerating statistics summary...")
    stats_rows = []
    for item in data:
        config = item['config']
        metrics = item['metrics']
        
        row = {'Configuration': config}
        
        # Build metrics - compute from all raw data
        if 'build' in metrics:
            if 'timings' in metrics['build'] and isinstance(metrics['build']['timings'], list):
                build_times = metrics['build']['timings']
                row['Avg Build Time (s)'] = round(np.mean(build_times), 2) if build_times else 'N/A'
            else:
                row['Avg Build Time (s)'] = 'N/A'
            row['Binary Size (MB)'] = metrics['build'].get('native', {}).get('binarySize', 'N/A')
        
        # Startup metrics - compute from all raw data
        if 'startup' in metrics:
            if 'timings' in metrics['startup'] and isinstance(metrics['startup']['timings'], list):
                startup_times = metrics['startup']['timings']
                row['Avg Startup Time (ms)'] = round(np.mean(startup_times), 2) if startup_times else 'N/A'
            else:
                row['Avg Startup Time (ms)'] = 'N/A'
        
        # Load metrics - compute from all raw data
        if 'load' in metrics:
            if 'throughput' in metrics['load'] and isinstance(metrics['load']['throughput'], list):
                throughput = metrics['load']['throughput']
                row['Avg Throughput (req/s)'] = round(np.mean(throughput), 2) if throughput else 'N/A'
            else:
                row['Avg Throughput (req/s)'] = 'N/A'
            
            if 'rss' in metrics['load'] and isinstance(metrics['load']['rss'], list):
                load_rss = metrics['load']['rss']
                row['Avg Max RSS (MB)'] = round(np.mean(load_rss), 2) if load_rss else 'N/A'
            else:
                row['Avg Max RSS (MB)'] = 'N/A'
            
            if 'throughputDensity' in metrics['load'] and isinstance(metrics['load']['throughputDensity'], list):
                density = metrics['load']['throughputDensity']
                row['Max Throughput Density'] = round(max(density), 2) if density else 'N/A'
            else:
                row['Max Throughput Density'] = 'N/A'
        
        stats_rows.append(row)
    
    stats_df = pd.DataFrame(stats_rows)
    # Sort by the same order as plots
    if config_order:
        stats_df['_sort_order'] = stats_df['Configuration'].map({c: i for i, c in enumerate(config_order)})
        stats_df = stats_df.sort_values('_sort_order').drop('_sort_order', axis=1)
    else:
        stats_df = stats_df.sort_values('Configuration')
    stats_df.to_csv('statistics_summary.csv', index=False)
    print("Saved: statistics_summary.csv")
    
    print("\n" + "="*60)
    print("Statistics Summary:")
    print("="*60)
    print(stats_df.to_string(index=False))
    
    print("\n" + "="*60)
    print("All plots generated successfully in the 'plots/' directory!")
    print("="*60)

if __name__ == '__main__':
    main()

# Made with Bob
