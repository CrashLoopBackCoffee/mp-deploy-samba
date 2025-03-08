"""Configuration model."""

import ipaddress
import os

import pulumi as p
import pydantic
import pydantic.alias_generators


class ConfigBaseModel(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(
        alias_generator=lambda s: s.replace('_', '-'),
        populate_by_name=True,
        extra='forbid',
    )


class EnvVarRef(ConfigBaseModel):
    envvar: str

    @property
    def value(self) -> p.Output[str]:
        return p.Output.secret(os.environ[self.envvar])


class ProxmoxConfig(ConfigBaseModel):
    node_name: str
    api_endpoint: pydantic.HttpUrl
    api_token: EnvVarRef
    verify_ssl: bool = True


class VirtualMachineConfig(ConfigBaseModel):
    name: str
    vmid: pydantic.PositiveInt

    cloud_image_url: pydantic.HttpUrl = pydantic.Field(
        default=pydantic.HttpUrl(
            'https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img'
        )
    )

    vlan_id: pydantic.PositiveInt | None = None
    ipv4_address: ipaddress.IPv4Interface

    cores: pydantic.PositiveInt
    memory_mb_min: pydantic.PositiveInt
    memory_mb_max: pydantic.PositiveInt

    root_disk_size_gb: pydantic.PositiveInt
    data_disk_size_gb: pydantic.PositiveInt
    data_disk_mount: str = '/mnt/data'

    ssh_user: str = 'ubuntu'
    ssh_public_key: str


class UnifyConfig(ConfigBaseModel):
    url: pydantic.HttpUrl = pydantic.HttpUrl('https://unifi/')
    verify_ssl: bool = False
    internal_domain: str = 'erx.box'


class SmbShare(ConfigBaseModel):
    name: str
    remote_write: bool
    k8s_write: bool


class SmbAccount(ConfigBaseModel):
    username: str
    password: str


class SmbConfig(ConfigBaseModel):
    remote: SmbAccount
    k8s: SmbAccount
    group: str = 'smb-users'
    shares: list[SmbShare]


class ComponentConfig(ConfigBaseModel):
    proxmox: ProxmoxConfig
    vm: VirtualMachineConfig
    unify: UnifyConfig = pydantic.Field(default_factory=UnifyConfig)
    smb: SmbConfig
