resource "openstack_compute_instance_v2" "minio_server" {
    name            = var.server_name
    image_name      = var.server_image
    flavor_name     = var.server_flavor
    key_pair        = openstack_compute_keypair_v2.terraform-key.name
    security_groups = ["default", openstack_networking_secgroup_v2.minio_security.name]

    # network {
    #   name = openstack_networking_network_v2.minio_network.name
    # }
    network {
        port = openstack_networking_port_v2.minio_port.id
    }
}
