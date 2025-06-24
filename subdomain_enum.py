import argparse
import subprocess
import threading
from datetime import datetime
import os
import re
import time

def is_tool_installed(tool_name):
    try:
        subprocess.run([tool_name, '--version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except FileNotFoundError:
        return False

def install_tool(tool_name):
    try:
        print(f"Installing {tool_name}...")
        subprocess.run(['sudo', 'apt-get', 'install', '-y', tool_name], check=True)
        print(f"{tool_name} installed successfully.")
    except subprocess.CalledProcessError:
        print(f"Failed to install {tool_name}. Please install it manually.")

def sanitize_filename(filename):
    return re.sub(r'[<>:"/\\|?*]', '_', filename)

def check_internet_connectivity():
    try:
        subprocess.run(['ping', '-c', '1', '8.8.8.8'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return True
    except subprocess.CalledProcessError:
        return False

def wait_for_internet():
    print("Internet connection lost. Pausing the process...")
    while not check_internet_connectivity():
        time.sleep(10)
    print("Internet connection restored. Resuming the process...")

def clone_nuclei_templates():
    template_path = os.path.expanduser("~/.nuclei-templates")
    if not os.path.isdir(template_path):
        print("Cloning nuclei-templates repository...")
        try:
            subprocess.run(['git', 'clone', 'https://github.com/projectdiscovery/nuclei-templates', template_path], check=True)
            print("nuclei-templates cloned successfully.")
        except subprocess.CalledProcessError as e:
            print(f"Failed to clone nuclei-templates: {e}")
            return False
    os.environ['NUCLEI_TEMPLATE_PATH'] = template_path
    return True

def remove_nuclei_templates():
    template_path = os.path.expanduser("~/.nuclei-templates")
    if os.path.isdir(template_path):
        print("Removing nuclei-templates directory...")
        try:
            subprocess.run(['rm', '-rf', template_path], check=True)
            print("nuclei-templates removed successfully.")
        except subprocess.CalledProcessError as e:
            print(f"Failed to remove nuclei-templates: {e}")

def run_subfinder(domain, result):
    print(f"Running Subfinder for domain: {domain}")
    command = ['subfinder', '-d', domain, '-silent']
    while not check_internet_connectivity():
        wait_for_internet()
    try:
        result_process = subprocess.run(command, capture_output=True, text=True, timeout=600)
        result_process.check_returncode()
        result.extend(result_process.stdout.splitlines())
    except subprocess.CalledProcessError as e:
        print(f"Error running Subfinder: {e}")
    except subprocess.TimeoutExpired:
        print("Subfinder process timed out.")

def run_fierce(domain, result):
    print(f"Running Fierce for domain: {domain}")
    command = ['fierce', '--domain', domain]
    while not check_internet_connectivity():
        wait_for_internet()
    try:
        result_process = subprocess.run(command, capture_output=True, text=True, timeout=600)
        result_process.check_returncode()
        result.extend(re.findall(r'Found: (.*?) \(', result_process.stdout))
    except subprocess.CalledProcessError as e:
        print(f"Error running Fierce: {e}")
    except subprocess.TimeoutExpired:
        print("Fierce process timed out.")

def run_nuclei(domain, result):
    if not clone_nuclei_templates():
        return

    print(f"Running Nuclei for domain: {domain}")
    command = ['nuclei', '-u', domain, '-t', os.getenv('NUCLEI_TEMPLATE_PATH')]
    while not check_internet_connectivity():
        wait_for_internet()
    try:
        result_process = subprocess.run(command, capture_output=True, text=True, timeout=600)
        result_process.check_returncode()
        result.extend(re.findall(r'\[INF\].*?(\S+)', result_process.stdout))
    except subprocess.CalledProcessError as e:
        print(f"Error running Nuclei: {e}")
        print(f"Command output: {e.output}")
        print(f"Command stderr: {e.stderr}")
    except subprocess.TimeoutExpired:
        print("Nuclei process timed out.")

def ping_subdomains(subdomains):
    reachable = []
    unreachable = []
    for subdomain in subdomains:
        print(f"Pinging {subdomain}...")
        try:
            result = subprocess.run(['ping', '-c', '1', subdomain], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if result.returncode == 0:
                reachable.append(subdomain)
            else:
                unreachable.append(subdomain)
        except subprocess.CalledProcessError:
            unreachable.append(subdomain)
        except subprocess.TimeoutExpired:
            unreachable.append(subdomain)
    return reachable, unreachable

def nslookup_subdomains(subdomains):
    ip_mapping = {}
    for subdomain in subdomains:
        print(f"Running nslookup for {subdomain}...")
        try:
            result = subprocess.run(['nslookup', subdomain], capture_output=True, text=True)
            if result.returncode == 0:
                ip_match = re.search(r"Address: (\S+)", result.stdout)
                if ip_match:
                    ip_mapping[subdomain] = ip_match.group(1)
                else:
                    ip_mapping[subdomain] = "IP not found"
            else:
                ip_mapping[subdomain] = "nslookup failed"
        except subprocess.CalledProcessError:
            ip_mapping[subdomain] = "nslookup failed"
    return ip_mapping

def find_subdomains(domain):
    subdomains = set()
    results_subfinder = []
    results_fierce = []
    results_nuclei = []

    threads = [
        threading.Thread(target=run_subfinder, args=(domain, results_subfinder)),
        threading.Thread(target=run_fierce, args=(domain, results_fierce)),
        threading.Thread(target=run_nuclei, args=(domain, results_nuclei))
    ]

    for thread in threads:
        thread.start()

    for thread in threads:
        thread.join()

    subdomains.update(results_subfinder)
    subdomains.update(results_fierce)
    subdomains.update(results_nuclei)

    print("Subdomain enumeration completed. Pinging subdomains...")

    unique_subdomains = list(subdomains)
    reachable_subdomains, unreachable_subdomains = ping_subdomains(unique_subdomains)
    
    print("Running nslookup on reachable subdomains...")
    ip_mapping = nslookup_subdomains(reachable_subdomains)

    timestamp = datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    output_file = f"{sanitize_filename(domain)}_{timestamp}_subdomains_report.txt"

    with open(output_file, 'w') as f:
        f.write("Reachable Subdomains:\n")
        for subdomain in reachable_subdomains:
            f.write(f"{subdomain}\n")

        f.write("\nUnreachable Subdomains:\n")
        for subdomain in unreachable_subdomains:
            f.write(f"{subdomain}\n")

        f.write("\nSubdomain IPs:\n")
        for subdomain, ip in ip_mapping.items():
            f.write(f"{subdomain}: {ip}\n")

    print(f"All results saved to {output_file}")

def install_dependencies():
    print("Installing required libraries...")
    subprocess.run(['pip', 'install', '-r', 'requirements.txt'], check=True)
    print("Dependencies installed successfully.")

def install_tools():
    print("Installing necessary tools...")
    with open('components.txt', 'r') as f:
        tools = f.read().splitlines()
    for tool in tools:
        install_tool(tool)

def uninstall_dependencies():
    print("Uninstalling libraries...")
    subprocess.run(['pip', 'uninstall', '-r', 'requirements.txt', '-y'], check=True)
    print("Dependencies uninstalled successfully.")

def uninstall_tools():
    print("Uninstalling necessary tools...")
    with open('components.txt', 'r') as f:
        tools = f.read().splitlines()
    for tool in tools:
        subprocess.run(['sudo', 'apt-get', 'remove', '-y', tool], check=True)
    print("Tools uninstalled successfully.")
    remove_nuclei_templates()

def main():
    parser = argparse.ArgumentParser(description='Unified tool for Subfinder, Fierce, and Nuclei.')
    parser.add_argument('-i', '--install', action='store_true', help='Install necessary tools and dependencies.')
    parser.add_argument('-f', '--find', type=str, help='Find subdomains for the given domain.')
    parser.add_argument('-r', '--remove', action='store_true', help='Remove all installed tools and dependencies.')

    args = parser.parse_args()

    if args.install:
        install_dependencies()
        install_tools()
    elif args.find:
        find_subdomains(args.find)
    elif args.remove:
        uninstall_dependencies()
        uninstall_tools()
    else:
        print("Invalid usage. Use -i to install tools, -f to find subdomains, or -r to remove tools.")

if __name__ == "__main__":
    main()
