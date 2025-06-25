# Subdomain Enumeration Tool

This is a beginner-friendly Python script to find subdomains of a given domain using tools like Subfinder, Fierce, and Nuclei.

It checks which subdomains are reachable, finds their IP addresses, and saves the results in a report file.

---

## 🔧 How to Use

### 1. Install tools and libraries
```bash
python3 subdomain_enum.py -i
````

### 2. Run the tool on a domain

```bash
python3 subdomain_enum.py -f example.com
```

### 3. Uninstall everything (if needed)

```bash
python3 subdomain_enum.py -r
```

---

## 📁 Files Included

* `subdomain_enum.py` – main script
* `components.txt` – list of tools to install
* `requirements.txt` – Python dependencies (empty for now)
* `README.md` – this file

---

## 📝 Output

The script creates a `.txt` report with:

* Reachable subdomains
* Unreachable subdomains
* IP addresses

---

## ⚠️ Important

This tool is for **educational and legal use only**. Do not use it on websites you do not own or have permission to test.

---

## 👨‍💻 Author

Made with ❤️ by Keisha 🚀

