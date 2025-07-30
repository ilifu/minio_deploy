# output "volumes" {
#   value = [
#     for v in openstack_compute_volume_attach_v2.minio_volume_attachment :
#     {
#       name   = v.volume_id
#       id     = v.id
#       device = v.device
#     }
#   ]
# }

resource "local_file" "ansible_inventory" {
  content = templatefile("templates/inventory.yaml.tpl",
    {
      floating_ip = openstack_networking_floatingip_v2.minio.address
      ssh_public_key = var.ssh_key_public
      domain_name = var.domain_name
      # volumes = [ for volume in openstack_blockstorage_volume_v3.minio_volume.*: volume ]
      volumes       = [for idx, v in openstack_compute_volume_attach_v2.minio_volume_attachment : {
        name   = openstack_blockstorage_volume_v3.minio_volume[idx].name
        id     = v.id
        volume_id = v.volume_id
        device = v.device
      }]
    }
  )
  filename = "inventory.yaml"
  file_permission = "0660"
}
