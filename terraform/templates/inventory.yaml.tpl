minio_servers:
  hosts:
    minio_server:
      ansible_host: ${ floating_ip }
  vars:
    ansible_connection: ssh
    ansible_ssh_common_args: '-o StrictHostKeyChecking=no -o ControlPersist=15m -i ${ ssh_public_key }'
    ansible_user: ubuntu
    domain_name: ${ domain_name }
    volumes:
%{ for volume in volumes ~}
      ${ volume.name }: ${ volume.id} (${ volume.device })
%{ endfor ~}
