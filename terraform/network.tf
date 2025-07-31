
resource "openstack_networking_network_v2" "minio_network" {
    name = "${var.server_name}-net"
    admin_state_up = "true"
}

data "openstack_networking_network_v2" "public" {
  name = var.floating_ip_pool
}


resource "openstack_networking_subnet_v2" "minio_subnet" {
    name = "${var.server_name}-subnet"
    network_id = openstack_networking_network_v2.minio_network.id
    cidr = "${var.cidr}"
    ip_version = 4
    enable_dhcp = "true"
    dns_nameservers = ["8.8.8.8"]
}

resource "openstack_networking_router_v2" "minio_router" {
  name                = "${var.server_name}-router"
  admin_state_up      = true
  external_network_id = data.openstack_networking_network_v2.public.id
}

resource "openstack_networking_router_interface_v2" "minio_router_interface" {
  router_id = openstack_networking_router_v2.minio_router.id
  subnet_id = openstack_networking_subnet_v2.minio_subnet.id
}

resource "openstack_networking_secgroup_v2" "minio_security" {
  name        = "${var.server_name}-security"
  description = "Workshop security group"
}

resource "openstack_networking_secgroup_rule_v2" "ssh" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 22
  port_range_max    = 22
  remote_ip_prefix  = "0.0.0.0/0"
  security_group_id = openstack_networking_secgroup_v2.minio_security.id
}

resource "openstack_networking_secgroup_rule_v2" "icmp" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "icmp"
  security_group_id = openstack_networking_secgroup_v2.minio_security.id
}

resource "openstack_networking_secgroup_rule_v2" "minio_ingress" {
  direction         = "ingress"
  ethertype         = "IPv4"
  protocol          = "tcp"
  port_range_min    = 443
  port_range_max    = 443
  remote_ip_prefix  = "0.0.0.0/0"
  security_group_id = openstack_networking_secgroup_v2.minio_security.id
}

resource "openstack_compute_keypair_v2" "terraform-key" {
  name   = "${var.server_name}-key"
  public_key = "${file(var.ssh_key_public)}"
}


resource "openstack_networking_floatingip_v2" "minio" {
  description  = format("fip-%s", var.server_name)
  pool = var.floating_ip_pool
}

# resource "openstack_networking_port_v2" "minio_port" {
#   name = "${var.server_name}-port"
#   device_id = openstack_compute_instance_v2.minio_server.id
#   network_id = openstack_networking_network_v2.minio_network.id
#   # fixed_ip = openstack_compute_instance_v2.minio_server.access_ip_v4
# }

# resource "openstack_networking_floatingip_associate_v2" "minio_floatingip_associate" {
#   floating_ip = openstack_networking_floatingip_v2.minio.address
#   port_id     = openstack_networking_port_v2.minio_port.id
# }

# resource "openstack_compute_floatingip_associate_v2" "minio" {
#   floating_ip = openstack_networking_floatingip_v2.minio.address
#   instance_id = openstack_compute_instance_v2.minio_server.id
# }


resource "openstack_networking_port_v2" "minio_port" {
  name       = "${var.server_name}-port"
  network_id = openstack_networking_network_v2.minio_network.id
  security_group_ids = [openstack_networking_secgroup_v2.minio_security.id]
}

resource "openstack_networking_floatingip_associate_v2" "minio_floatingip_associate" {
  floating_ip = openstack_networking_floatingip_v2.minio.address
  port_id     = openstack_networking_port_v2.minio_port.id
}
