minio_servers:
  hosts:
    minio_server:
      ansible_host: ${ floating_ip }
  vars:
    ansible_connection: ssh
    ansible_ssh_common_args: '-o StrictHostKeyChecking=no -o ControlPersist=15m -i ${ ssh_public_key }'
    ansible_user: ubuntu
    domain_name: ${ domain_name }
    public_ip: ${ floating_ip }
    private_ip: ${ private_ip }
    locale: ${ locale }
    timezone: ${ timezone }
    minio_admin_password: ${ minio_admin_password }
    volumes:
%{ for volume in volumes ~}
      ${ volume.name }:
        id: ${ volume.id}
        volume_id: ${ volume.volume_id }
        device: ${ volume.device }
        label: ${ volume.label }
%{ endfor ~}
