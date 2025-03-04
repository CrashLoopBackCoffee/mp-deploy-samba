import pathlib

import jinja2
import pulumi as p
import pulumi_proxmoxve as proxmoxve

from samba.model import ComponentConfig


def create_server(component_config: ComponentConfig, proxmox_provider: proxmoxve.Provider):
    proxmox_opts = p.ResourceOptions(provider=proxmox_provider)

    cloud_image = proxmoxve.download.File(
        'cloud-image',
        content_type='iso',
        datastore_id='local',
        node_name=component_config.proxmox.node_name,
        overwrite=False,
        overwrite_unmanaged=True,
        url=str(component_config.vm.cloud_image_url),
        opts=p.ResourceOptions.merge(
            proxmox_opts,
            p.ResourceOptions(retain_on_delete=True),
        ),
    )

    cloud_config_template = jinja2.Template(
        pathlib.Path('assets/cloud-init/cloud-config.yaml').read_text(),
        undefined=jinja2.StrictUndefined,
    )

    stack_name = p.get_stack()

    cloud_config = proxmoxve.storage.File(
        'cloud-config',
        node_name=component_config.proxmox.node_name,
        datastore_id='local',
        content_type='snippets',
        source_raw={
            'data': cloud_config_template.render(
                component_config.vm.model_dump()
                | {
                    'username': component_config.vm.ssh_user,
                    'ssh_public_key': component_config.vm.ssh_public_key,
                    'data_disk_mount': component_config.vm.data_disk_mount,
                }
            ),
            'file_name': f'cloud-config-{component_config.vm.name}.yaml',
        },
        opts=p.ResourceOptions.merge(
            proxmox_opts,
            p.ResourceOptions(delete_before_replace=True),
        ),
    )

    gateway_address = str(component_config.vm.ipv4_address.network.network_address + 1)

    vlan_config: proxmoxve.vm.VirtualMachineNetworkDeviceArgsDict = (
        {'vlan_id': int(component_config.vm.vlan_id)} if component_config.vm.vlan_id else {}
    )

    vm = proxmoxve.vm.VirtualMachine(
        component_config.vm.name,
        name=component_config.vm.name,
        node_name=component_config.proxmox.node_name,
        vm_id=component_config.vm.vmid,
        tags=[stack_name],
        description='Kubernetes Master, maintained with Pulumi.',
        cpu={
            'cores': component_config.vm.cores,
            # use exact CPU flags of host, as migration of VM for k8s nodes is irrelevant:
            'type': 'host',
        },
        memory={
            'dedicated': component_config.vm.memory_mb_max,
            'floating': component_config.vm.memory_mb_min,
        },
        cdrom={'enabled': False},
        disks=[
            {
                'interface': 'virtio0',
                'size': component_config.vm.root_disk_size_gb,
                'file_id': cloud_image.id,
                'iothread': True,
                'discard': 'on',
                'file_format': 'raw',
                # hack to avoid diff in subsequent runs:
                'speed': {
                    'read': 10000,
                },
            },
            {
                'interface': 'virtio1',
                'size': component_config.vm.data_disk_size_gb,
                'iothread': True,
                'discard': 'on',
                'file_format': 'raw',
                # hack to avoid diff in subsequent runs:
                'speed': {
                    'read': 10000,
                },
            },
        ],
        network_devices=[
            {
                'bridge': 'vmbr0',
                'model': 'virtio',
                **vlan_config,
            }
        ],
        agent={'enabled': True},
        initialization={
            'ip_configs': [
                {
                    'ipv4': {
                        'address': str(component_config.vm.ipv4_address),
                        'gateway': gateway_address,
                    }
                }
            ],
            'dns': {
                'domain': 'local',
                'servers': [gateway_address],
            },
            'user_data_file_id': cloud_config.id,
        },
        stop_on_destroy=True,
        on_boot=stack_name == 'prod',
        machine='q35',
        # Linux 2.6+:
        operating_system={'type': 'l26'},
        opts=p.ResourceOptions.merge(
            proxmox_opts,
            p.ResourceOptions(ignore_changes=['cdrom']),
        ),
    )
