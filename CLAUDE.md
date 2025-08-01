# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This repository contains infrastructure and tooling for MinIO S3 object storage deployment on OpenStack clouds. It consists of two main components:

1. **Infrastructure deployment** (Terraform + Ansible) - Automated provisioning and configuration of MinIO servers
2. **MinIO TUI** (Python/Textual) - A terminal user interface for interacting with MinIO instances

## Common Development Commands

### Infrastructure Deployment

Navigate to project root for all infrastructure commands:

```bash
# Terraform operations
cd terraform
terraform init
terraform plan
terraform apply

# Ansible deployment (run from project root)
ansible-playbook -i terraform/inventory.yaml ansible/site.yaml
```

### MinIO TUI Development

Navigate to `scripts/` directory for all TUI development:

```bash
# Install in development mode
cd scripts
pip install .

# Run the TUI
minio-tui

# Run tests
python -m pytest tests/
```

## Architecture

### Infrastructure Components

- **Terraform** (`terraform/`): Provisions OpenStack resources (VMs, volumes, networking)
- **Ansible** (`ansible/`): Configures servers with four roles:
  - `base`: Basic server setup (locale, timezone, packages)
  - `xfs_mounts`: Formats and mounts storage volumes as XFS
  - `caddy`: Reverse proxy for HTTPS access
  - `minio`: MinIO server installation and configuration

### MinIO TUI Architecture

Located in `scripts/minio_tui/`:

- **`app.py`**: Main Textual TUI application with modal screens for bucket/object operations
- **`minio_client.py`**: Boto3-based wrapper for MinIO S3 API operations
- **`config.py`**: Dynaconf-based configuration management (supports config.toml, .env, environment variables)
- **`run.py`**: Entry point script

The TUI uses a two-panel layout: bucket list (left) and object tree view (right) with context-sensitive keybindings.

## Configuration

### Infrastructure Configuration

Set variables in `terraform/terraform.tfvars`:
- `ssh_key_public`: SSH public key for server access
- `domain_name`: Domain for MinIO server (required)
- `server_flavor`, `server_image`: OpenStack instance specifications
- `minio_volume_*`: Storage configuration

### MinIO TUI Configuration

Configuration priority: environment variables → .env file → config.toml

Required settings:
```toml
[minio]
endpoint_url = "https://your-minio-domain.com"
access_key = "your-access-key"
secret_key = "your-secret-key"
```

Environment variables use prefix `MINIO_TUI_` (e.g., `MINIO_TUI_MINIO_SECRET_KEY`).

## Project Structure

```
├── terraform/          # Infrastructure as code
├── ansible/            # Server configuration
│   ├── site.yaml       # Main playbook
│   └── roles/          # Ansible roles (base, caddy, minio, xfs_mounts)
└── scripts/            # MinIO TUI application
    ├── minio_tui/      # Main application code
    ├── tests/          # Test suite
    └── pyproject.toml  # Python package configuration
```

## Testing

The TUI includes unit tests for configuration and MinIO client functionality. Tests use mocked dependencies and can be run with pytest from the `scripts/` directory.