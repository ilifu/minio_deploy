variable "ssh_key_public" {
  type = string
}
variable "floating_ip_pool" {
  type = string
  default = "Ext_Floating_IP"
}

variable "server_name" {
  type = string
  default = "minio"
}
variable "cidr" {
  type    = string
  default = "192.168.90.0/24"
}
variable "server_flavor" {
  type = string
  default = "ilifu-B"
}
variable "domain_name" {
  type = string
}
variable "server_image" {
  type = string
  default = "20250728-noble"
}

variable "minio_volume_size_gib" {
  type = number
  default = 64
}

variable "minio_volume_count" {
  type = number
  default = 4
}

variable "minio_volume_name_prefix" {
    type = string
    default = "minio-data"
}

variable "locale" {
  type = string
  default = "en_ZA.UTF-8"
}

variable "timezone" {
  type = string
  default = "Africa/Johannesburg"
}
