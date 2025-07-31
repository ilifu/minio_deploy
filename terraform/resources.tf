resource "random_password" "minio_admin_password" {
  length  = 20
  special = true
}

resource "local_file" "ansible_inventory" {
  content = templatefile("templates/inventory.yaml.tpl",
    {
      floating_ip = openstack_networking_floatingip_v2.minio.address
      private_ip = openstack_compute_instance_v2.minio_server.access_ip_v4
      ssh_public_key = var.ssh_key_public
      domain_name = var.domain_name
      # volumes = [ for volume in openstack_blockstorage_volume_v3.minio_volume.*: volume ]
      volumes       = [for idx, v in openstack_compute_volume_attach_v2.minio_volume_attachment : {
        name   = openstack_blockstorage_volume_v3.minio_volume[idx].name
        id     = v.id
        volume_id = v.volume_id
        device = v.device
        label = "MINIODRIVE${idx + 1}"
      }]
      locale = var.locale
      timezone = var.timezone
      minio_admin_password = random_password.minio_admin_password.result
    }
  )
  filename = "inventory.yaml"
  file_permission = "0660"
}
