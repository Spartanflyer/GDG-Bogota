"""Cloud Function (nicely deployed in deployment) DM template."""

import base64
import json
import zipfile
import hashlib
from StringIO import StringIO


def GenerateConfig(ctx):
    """Generate YAML resource configuration."""
    inMemoryOutputFile = StringIO()
    function_name = ctx.env['deployment'] + 'cf'
    source_archive_url = ctx.properties['sourceArchiveUrl']
    zip_file = zipfile.ZipFile(inMemoryOutputFile, mode='w', compression=zipfile.ZIP_DEFLATED)
    for imp in ctx.imports:
        if imp.startswith(ctx.properties['codeLocation']):
            zip_file.writestr(imp[len(ctx.properties['codeLocation']):], ctx.imports[imp])
    zip_file.close()
    content = base64.b64encode(inMemoryOutputFile.getvalue())
    m = hashlib.md5()
    m.update(content)

    cmd = "echo '" + content + "' | base64 -d > /functions/functions.zip;"
    volumes = [{
        'name': 'functions-code',
        'path': '/functions'
    }]
    build_step = {
        'name': 'upload-functions-code',
        'action': 'gcp-types/cloudbuild-v1:cloudbuild.projects.builds.create',
        'metadata': {
            'runtimePolicy': ['UPDATE_ON_CHANGE']
        },
        'properties': {
            'steps': [{
                'name': 'ubuntu',
                'args': ['bash', '-c', cmd],
                'volumes': volumes,
            }, {
                'name': 'gcr.io/cloud-builders/gsutil',
                'args': ['cp', '/functions/functions.zip', source_archive_url],
                'volumes': volumes
            }],
            'timeout': '120s'
        }
    }
    cloud_function = {
        'type': 'gcp-types/cloudfunctions-v1beta2:projects.locations.functions',
        'name': function_name,
        'properties': {
            'location': ctx.properties['location'],
            'functions': function_name,
            'labels': {
                # Add the hash of the contents to trigger an update if the bucket
                # object changes
                'content-md5': m.hexdigest()
            },
            'sourceArchiveUrl': source_archive_url,
            'entryPoint': ctx.properties['entryPoint'],
            'httpsTrigger': {},
            'timeout': ctx.properties['timeout'],
            'availableMemoryMb': ctx.properties['availableMemoryMb']
        },
        'metadata': {
            'dependsOn': ['upload-functions-code']
        }
    }
    resources = [build_step, cloud_function]

    return {
        'resources': resources,
        'outputs': [
            {
                'name': 'sourceArchiveUrl',
                'value': source_archive_url
            },
            {
                'name': 'name',
                'value': '$(ref.' + function_name + '.name)'
            }
        ]
    }
