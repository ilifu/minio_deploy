terraform {
  required_version = ">= 1.1.9"
  required_providers {
    openstack = {
      source  = "terraform-provider-openstack/openstack"
      version = ">= 3.3.2"
    }
  }
}

# provider "openstack" {
#   required_version = ">= 3.3.2"
# }
