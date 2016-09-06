import os
from fabric.api import task, local, run, settings, execute, put
import fabric.contrib as fcontrib
import cliqz
import cliqz_tasks
from cliqz_tasks.ec2 import launch_cluster, cluster_list_instances, for_all
from cliqz_tasks.autoscale import update, update_config_from_instance

app_name = 'Adblocking_load_filters_test'
APP_ROOT = os.path.dirname(os.path.abspath(__file__))


@task
def install_luigi():
    cliqz.cli.ensure_dir('/etc/luigi')
    cliqz.cli.put('conf/luigi-server.init', '/etc/init.d/luigid', True, mode=777)
    # cliqz.cli.put('conf/luigi.cfg', '/etc/luigi/client.cfg', True)
    cliqz.cli.restart_service('luigid', 5)


@task
def full_install(host_details=None):
    prepare_host()
    install_luigi()
    deploy_app()


@task
def prepare_host(host_details=None):
    # set up locale
    run("echo 'export LC_ALL=\"en_US.UTF-8\"' >> /etc/environment")
    run("echo 'export AWS_DEFAULT_REGION=\"us-east-1\"' >> /etc/environment")
    cliqz.cli.system_package('python-pip', 'gcc', 'make', 'python-dev', 'git',
                             'libevent-dev', 'emacs', 'zip')
    cliqz.cli.python_package('ipython', 'ujson', 'luigi', 'pyyaml', 'boto', 'requests', 'requests[security]')


@task
def deploy_app():
    pkg = cliqz.package.gen_definition()
    with settings(host_string='localhost'):
        local("tar cjf {} load_filters".format(pkg['local']))
    cliqz.package.install(pkg, '/opt/load_filters')
    add_crontab()


@task
def add_crontab():
    cliqz.cli.install_cronjob(
        "0 3 * * * root cd /opt/load_filters/load_filters && PYTHONPATH='.' /usr/local/bin/luigi --module load_filters StoreAdblockerFilters",
        "DailyLoadFilters")


@task
# to be removed
def upload_allowed_lists():
    with settings(host_string='localhost'):
        local('aws s3 cp conf/allowed-lists s3://cdn.cliqz.com/adblocking/allowed-lists.json')


@task
def add_entry_allowed_lists(list, url, lang=None):
    run("python /opt/load_filters/load_filters/update_allowed_lists.py {0} {1} {2}".format(list, url, lang))

# Setup
cliqz.setup(
    app_name=app_name,
    project_owners=['ghadir'],
    elb={'name': app_name},
    buckets=[],
    policies=[
        {
            "Action": [
                "*"
            ],
            "Resource": [
                "arn:aws:s3:::cdn.cliqz.com*"
            ],
            "Effect": "Allow"
        },
        {
            "Action": [
                "*"
            ],
            "Resource": [
                "arn:aws:s3:::cliqz-mapreduce*"
            ],
            "Effect": "Allow"
        }
        ],
    cluster={
        'primary_install': full_install,
        'use_vpc': True,
        'name': app_name,
        'image': 'ubuntu-14.04-64bit',
        'autoscale_launch_data': '\n'.join(['service luigid restart']),
        'instances': [
            {
                'price_zone': 'c1',
                'spot_price': 0.5,
                'ebs_size': 20,
                'ebs_type': 'gp2',
                'num_instances': 1,
                'instance_type': 'm1.medium',
            },
        ],
    },
    security_rules=[
        {
            'ip_protocol': 'tcp',
            'from_port': 80,
            'to_port': 80,
            'cidr_ip': '0.0.0.0/0'
        }
    ]
)
