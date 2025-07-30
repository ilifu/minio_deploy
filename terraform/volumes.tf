resource "openstack_blockstorage_volume_v3" "minio_volume" {
  count       = var.minio_volume_count
  name        = format("${var.minio_volume_name_prefix}-%02s", count.index + 1)
  size        = var.minio_volume_size_gib
  description = "Volume for MinIO server"
}

resource "openstack_compute_volume_attach_v2" "minio_volume_attachment" {
  count        = var.minio_volume_count
  volume_id    = openstack_blockstorage_volume_v3.minio_volume[count.index].id
  instance_id  = openstack_compute_instance_v2.minio_server.id
  # device       = format("/dev/vd%02s", (count.index + 1))
  # host_name    = openstack_compute_instance_v2.minio_server.name
}

