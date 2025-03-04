"""Kubernetes stack."""

import pulumi as p
import pulumi_proxmoxve as proxmoxve

from samba.app import create_server
from samba.model import ComponentConfig

component_config = ComponentConfig.model_validate(p.Config().require_object('config'))

proxmox_provider = proxmoxve.Provider(
    'provider',
    endpoint=str(component_config.proxmox.api_endpoint),
    api_token=component_config.proxmox.api_token.value,
    insecure=not component_config.proxmox.verify_ssl,
    ssh={
        'username': 'root',
        'agent': True,
    },
)

create_server(component_config, proxmox_provider)
