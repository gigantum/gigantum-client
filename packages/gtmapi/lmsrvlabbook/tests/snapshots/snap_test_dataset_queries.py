# -*- coding: utf-8 -*-
# snapshottest: v1 - https://goo.gl/zC4yUc
from __future__ import unicode_literals

from snapshottest import Snapshot


snapshots = Snapshot()

snapshots['TestDatasetQueries.test_pagination_noargs 1'] = {
    'data': {
        'datasetList': {
            'localDatasets': {
                'edges': [
                    {
                        'cursor': 'MA==',
                        'node': {
                            'description': 'Cats 1',
                            'name': 'dataset1'
                        }
                    },
                    {
                        'cursor': 'MQ==',
                        'node': {
                            'description': 'Cats 2',
                            'name': 'dataset2'
                        }
                    },
                    {
                        'cursor': 'Mg==',
                        'node': {
                            'description': 'Cats 3',
                            'name': 'dataset3'
                        }
                    },
                    {
                        'cursor': 'Mw==',
                        'node': {
                            'description': 'Cats 4',
                            'name': 'dataset4'
                        }
                    },
                    {
                        'cursor': 'NA==',
                        'node': {
                            'description': 'Cats 5',
                            'name': 'dataset5'
                        }
                    },
                    {
                        'cursor': 'NQ==',
                        'node': {
                            'description': 'Cats 6',
                            'name': 'dataset6'
                        }
                    },
                    {
                        'cursor': 'Ng==',
                        'node': {
                            'description': 'Cats 7',
                            'name': 'dataset7'
                        }
                    },
                    {
                        'cursor': 'Nw==',
                        'node': {
                            'description': 'Cats 8',
                            'name': 'dataset8'
                        }
                    },
                    {
                        'cursor': 'OA==',
                        'node': {
                            'description': 'Cats 9',
                            'name': 'dataset9'
                        }
                    },
                    {
                        'cursor': 'OQ==',
                        'node': {
                            'description': 'Cats other',
                            'name': 'dataset-other'
                        }
                    }
                ],
                'pageInfo': {
                    'hasNextPage': False,
                    'hasPreviousPage': False
                }
            }
        }
    }
}

snapshots['TestDatasetQueries.test_pagination_sort_az_reverse 1'] = {
    'data': {
        'datasetList': {
            'localDatasets': {
                'edges': [
                    {
                        'cursor': 'MA==',
                        'node': {
                            'datasetType': {
                                'description': 'Dataset storage provided by your Gigantum account supporting files up to 5GB in size',
                                'name': 'Gigantum Cloud',
                                'storageType': 'gigantum_object_v1'
                            },
                            'description': 'Cats other',
                            'id': 'RGF0YXNldDp0ZXN0MyZkYXRhc2V0LW90aGVy',
                            'name': 'dataset-other'
                        }
                    },
                    {
                        'cursor': 'MQ==',
                        'node': {
                            'datasetType': {
                                'description': 'Dataset storage provided by your Gigantum account supporting files up to 5GB in size',
                                'name': 'Gigantum Cloud',
                                'storageType': 'gigantum_object_v1'
                            },
                            'description': 'Cats 9',
                            'id': 'RGF0YXNldDpkZWZhdWx0JmRhdGFzZXQ5',
                            'name': 'dataset9'
                        }
                    },
                    {
                        'cursor': 'Mg==',
                        'node': {
                            'datasetType': {
                                'description': 'Dataset storage provided by your Gigantum account supporting files up to 5GB in size',
                                'name': 'Gigantum Cloud',
                                'storageType': 'gigantum_object_v1'
                            },
                            'description': 'Cats 8',
                            'id': 'RGF0YXNldDpkZWZhdWx0JmRhdGFzZXQ4',
                            'name': 'dataset8'
                        }
                    },
                    {
                        'cursor': 'Mw==',
                        'node': {
                            'datasetType': {
                                'description': 'Dataset storage provided by your Gigantum account supporting files up to 5GB in size',
                                'name': 'Gigantum Cloud',
                                'storageType': 'gigantum_object_v1'
                            },
                            'description': 'Cats 7',
                            'id': 'RGF0YXNldDpkZWZhdWx0JmRhdGFzZXQ3',
                            'name': 'dataset7'
                        }
                    },
                    {
                        'cursor': 'NA==',
                        'node': {
                            'datasetType': {
                                'description': 'Dataset storage provided by your Gigantum account supporting files up to 5GB in size',
                                'name': 'Gigantum Cloud',
                                'storageType': 'gigantum_object_v1'
                            },
                            'description': 'Cats 6',
                            'id': 'RGF0YXNldDpkZWZhdWx0JmRhdGFzZXQ2',
                            'name': 'dataset6'
                        }
                    },
                    {
                        'cursor': 'NQ==',
                        'node': {
                            'datasetType': {
                                'description': 'Dataset storage provided by your Gigantum account supporting files up to 5GB in size',
                                'name': 'Gigantum Cloud',
                                'storageType': 'gigantum_object_v1'
                            },
                            'description': 'Cats 5',
                            'id': 'RGF0YXNldDpkZWZhdWx0JmRhdGFzZXQ1',
                            'name': 'dataset5'
                        }
                    },
                    {
                        'cursor': 'Ng==',
                        'node': {
                            'datasetType': {
                                'description': 'Dataset storage provided by your Gigantum account supporting files up to 5GB in size',
                                'name': 'Gigantum Cloud',
                                'storageType': 'gigantum_object_v1'
                            },
                            'description': 'Cats 4',
                            'id': 'RGF0YXNldDpkZWZhdWx0JmRhdGFzZXQ0',
                            'name': 'dataset4'
                        }
                    },
                    {
                        'cursor': 'Nw==',
                        'node': {
                            'datasetType': {
                                'description': 'Dataset storage provided by your Gigantum account supporting files up to 5GB in size',
                                'name': 'Gigantum Cloud',
                                'storageType': 'gigantum_object_v1'
                            },
                            'description': 'Cats 3',
                            'id': 'RGF0YXNldDpkZWZhdWx0JmRhdGFzZXQz',
                            'name': 'dataset3'
                        }
                    },
                    {
                        'cursor': 'OA==',
                        'node': {
                            'datasetType': {
                                'description': 'Dataset storage provided by your Gigantum account supporting files up to 5GB in size',
                                'name': 'Gigantum Cloud',
                                'storageType': 'gigantum_object_v1'
                            },
                            'description': 'Cats 2',
                            'id': 'RGF0YXNldDpkZWZhdWx0JmRhdGFzZXQy',
                            'name': 'dataset2'
                        }
                    },
                    {
                        'cursor': 'OQ==',
                        'node': {
                            'datasetType': {
                                'description': 'Dataset storage provided by your Gigantum account supporting files up to 5GB in size',
                                'name': 'Gigantum Cloud',
                                'storageType': 'gigantum_object_v1'
                            },
                            'description': 'Cats 1',
                            'id': 'RGF0YXNldDpkZWZhdWx0JmRhdGFzZXQx',
                            'name': 'dataset1'
                        }
                    }
                ],
                'pageInfo': {
                    'hasNextPage': False,
                    'hasPreviousPage': False
                }
            }
        }
    }
}

snapshots['TestDatasetQueries.test_pagination_sort_create 1'] = {
    'data': {
        'datasetList': {
            'localDatasets': {
                'edges': [
                    {
                        'cursor': 'MA==',
                        'node': {
                            'description': 'Cats 2',
                            'id': 'RGF0YXNldDpkZWZhdWx0JmRhdGFzZXQy',
                            'name': 'dataset2'
                        }
                    },
                    {
                        'cursor': 'MQ==',
                        'node': {
                            'description': 'Cats 3',
                            'id': 'RGF0YXNldDpkZWZhdWx0JmRhdGFzZXQz',
                            'name': 'dataset3'
                        }
                    },
                    {
                        'cursor': 'Mg==',
                        'node': {
                            'description': 'Cats 4',
                            'id': 'RGF0YXNldDpkZWZhdWx0JmRhdGFzZXQ0',
                            'name': 'dataset4'
                        }
                    },
                    {
                        'cursor': 'Mw==',
                        'node': {
                            'description': 'Cats 5',
                            'id': 'RGF0YXNldDpkZWZhdWx0JmRhdGFzZXQ1',
                            'name': 'dataset5'
                        }
                    },
                    {
                        'cursor': 'NA==',
                        'node': {
                            'description': 'Cats 6',
                            'id': 'RGF0YXNldDpkZWZhdWx0JmRhdGFzZXQ2',
                            'name': 'dataset6'
                        }
                    },
                    {
                        'cursor': 'NQ==',
                        'node': {
                            'description': 'Cats 7',
                            'id': 'RGF0YXNldDpkZWZhdWx0JmRhdGFzZXQ3',
                            'name': 'dataset7'
                        }
                    },
                    {
                        'cursor': 'Ng==',
                        'node': {
                            'description': 'Cats 8',
                            'id': 'RGF0YXNldDpkZWZhdWx0JmRhdGFzZXQ4',
                            'name': 'dataset8'
                        }
                    },
                    {
                        'cursor': 'Nw==',
                        'node': {
                            'description': 'Cats 9',
                            'id': 'RGF0YXNldDpkZWZhdWx0JmRhdGFzZXQ5',
                            'name': 'dataset9'
                        }
                    },
                    {
                        'cursor': 'OA==',
                        'node': {
                            'description': 'Cats other',
                            'id': 'RGF0YXNldDp0ZXN0MyZkYXRhc2V0LW90aGVy',
                            'name': 'dataset-other'
                        }
                    },
                    {
                        'cursor': 'OQ==',
                        'node': {
                            'description': 'Cats 1',
                            'id': 'RGF0YXNldDpkZWZhdWx0JmRhdGFzZXQx',
                            'name': 'dataset1'
                        }
                    }
                ],
                'pageInfo': {
                    'hasNextPage': False,
                    'hasPreviousPage': False
                }
            }
        }
    }
}

snapshots['TestDatasetQueries.test_pagination_sort_create_desc 1'] = {
    'data': {
        'datasetList': {
            'localDatasets': {
                'edges': [
                    {
                        'cursor': 'MA==',
                        'node': {
                            'description': 'Cats 1',
                            'id': 'RGF0YXNldDpkZWZhdWx0JmRhdGFzZXQx',
                            'name': 'dataset1'
                        }
                    },
                    {
                        'cursor': 'MQ==',
                        'node': {
                            'description': 'Cats other',
                            'id': 'RGF0YXNldDp0ZXN0MyZkYXRhc2V0LW90aGVy',
                            'name': 'dataset-other'
                        }
                    },
                    {
                        'cursor': 'Mg==',
                        'node': {
                            'description': 'Cats 9',
                            'id': 'RGF0YXNldDpkZWZhdWx0JmRhdGFzZXQ5',
                            'name': 'dataset9'
                        }
                    },
                    {
                        'cursor': 'Mw==',
                        'node': {
                            'description': 'Cats 8',
                            'id': 'RGF0YXNldDpkZWZhdWx0JmRhdGFzZXQ4',
                            'name': 'dataset8'
                        }
                    },
                    {
                        'cursor': 'NA==',
                        'node': {
                            'description': 'Cats 7',
                            'id': 'RGF0YXNldDpkZWZhdWx0JmRhdGFzZXQ3',
                            'name': 'dataset7'
                        }
                    },
                    {
                        'cursor': 'NQ==',
                        'node': {
                            'description': 'Cats 6',
                            'id': 'RGF0YXNldDpkZWZhdWx0JmRhdGFzZXQ2',
                            'name': 'dataset6'
                        }
                    },
                    {
                        'cursor': 'Ng==',
                        'node': {
                            'description': 'Cats 5',
                            'id': 'RGF0YXNldDpkZWZhdWx0JmRhdGFzZXQ1',
                            'name': 'dataset5'
                        }
                    },
                    {
                        'cursor': 'Nw==',
                        'node': {
                            'description': 'Cats 4',
                            'id': 'RGF0YXNldDpkZWZhdWx0JmRhdGFzZXQ0',
                            'name': 'dataset4'
                        }
                    },
                    {
                        'cursor': 'OA==',
                        'node': {
                            'description': 'Cats 3',
                            'id': 'RGF0YXNldDpkZWZhdWx0JmRhdGFzZXQz',
                            'name': 'dataset3'
                        }
                    },
                    {
                        'cursor': 'OQ==',
                        'node': {
                            'description': 'Cats 2',
                            'id': 'RGF0YXNldDpkZWZhdWx0JmRhdGFzZXQy',
                            'name': 'dataset2'
                        }
                    }
                ],
                'pageInfo': {
                    'hasNextPage': False,
                    'hasPreviousPage': False
                }
            }
        }
    }
}

snapshots['TestDatasetQueries.test_pagination_sort_modified 1'] = {
    'data': {
        'datasetList': {
            'localDatasets': {
                'edges': [
                    {
                        'cursor': 'MA==',
                        'node': {
                            'description': 'Cats 1',
                            'id': 'RGF0YXNldDpkZWZhdWx0JmRhdGFzZXQx',
                            'name': 'dataset1'
                        }
                    },
                    {
                        'cursor': 'MQ==',
                        'node': {
                            'description': 'Cats other',
                            'id': 'RGF0YXNldDp0ZXN0MyZkYXRhc2V0LW90aGVy',
                            'name': 'dataset-other'
                        }
                    },
                    {
                        'cursor': 'Mg==',
                        'node': {
                            'description': 'Cats 9',
                            'id': 'RGF0YXNldDpkZWZhdWx0JmRhdGFzZXQ5',
                            'name': 'dataset9'
                        }
                    },
                    {
                        'cursor': 'Mw==',
                        'node': {
                            'description': 'Cats 8',
                            'id': 'RGF0YXNldDpkZWZhdWx0JmRhdGFzZXQ4',
                            'name': 'dataset8'
                        }
                    },
                    {
                        'cursor': 'NA==',
                        'node': {
                            'description': 'Cats 7',
                            'id': 'RGF0YXNldDpkZWZhdWx0JmRhdGFzZXQ3',
                            'name': 'dataset7'
                        }
                    },
                    {
                        'cursor': 'NQ==',
                        'node': {
                            'description': 'Cats 6',
                            'id': 'RGF0YXNldDpkZWZhdWx0JmRhdGFzZXQ2',
                            'name': 'dataset6'
                        }
                    },
                    {
                        'cursor': 'Ng==',
                        'node': {
                            'description': 'Cats 5',
                            'id': 'RGF0YXNldDpkZWZhdWx0JmRhdGFzZXQ1',
                            'name': 'dataset5'
                        }
                    },
                    {
                        'cursor': 'Nw==',
                        'node': {
                            'description': 'Cats 4',
                            'id': 'RGF0YXNldDpkZWZhdWx0JmRhdGFzZXQ0',
                            'name': 'dataset4'
                        }
                    },
                    {
                        'cursor': 'OA==',
                        'node': {
                            'description': 'Cats 3',
                            'id': 'RGF0YXNldDpkZWZhdWx0JmRhdGFzZXQz',
                            'name': 'dataset3'
                        }
                    },
                    {
                        'cursor': 'OQ==',
                        'node': {
                            'description': 'Cats 2',
                            'id': 'RGF0YXNldDpkZWZhdWx0JmRhdGFzZXQy',
                            'name': 'dataset2'
                        }
                    }
                ],
                'pageInfo': {
                    'hasNextPage': False,
                    'hasPreviousPage': False
                }
            }
        }
    }
}

snapshots['TestDatasetQueries.test_pagination_sort_modified 2'] = {
    'data': {
        'datasetList': {
            'localDatasets': {
                'edges': [
                    {
                        'cursor': 'MA==',
                        'node': {
                            'description': 'Cats 4',
                            'id': 'RGF0YXNldDpkZWZhdWx0JmRhdGFzZXQ0',
                            'name': 'dataset4'
                        }
                    },
                    {
                        'cursor': 'MQ==',
                        'node': {
                            'description': 'Cats 1',
                            'id': 'RGF0YXNldDpkZWZhdWx0JmRhdGFzZXQx',
                            'name': 'dataset1'
                        }
                    },
                    {
                        'cursor': 'Mg==',
                        'node': {
                            'description': 'Cats other',
                            'id': 'RGF0YXNldDp0ZXN0MyZkYXRhc2V0LW90aGVy',
                            'name': 'dataset-other'
                        }
                    },
                    {
                        'cursor': 'Mw==',
                        'node': {
                            'description': 'Cats 9',
                            'id': 'RGF0YXNldDpkZWZhdWx0JmRhdGFzZXQ5',
                            'name': 'dataset9'
                        }
                    },
                    {
                        'cursor': 'NA==',
                        'node': {
                            'description': 'Cats 8',
                            'id': 'RGF0YXNldDpkZWZhdWx0JmRhdGFzZXQ4',
                            'name': 'dataset8'
                        }
                    },
                    {
                        'cursor': 'NQ==',
                        'node': {
                            'description': 'Cats 7',
                            'id': 'RGF0YXNldDpkZWZhdWx0JmRhdGFzZXQ3',
                            'name': 'dataset7'
                        }
                    },
                    {
                        'cursor': 'Ng==',
                        'node': {
                            'description': 'Cats 6',
                            'id': 'RGF0YXNldDpkZWZhdWx0JmRhdGFzZXQ2',
                            'name': 'dataset6'
                        }
                    },
                    {
                        'cursor': 'Nw==',
                        'node': {
                            'description': 'Cats 5',
                            'id': 'RGF0YXNldDpkZWZhdWx0JmRhdGFzZXQ1',
                            'name': 'dataset5'
                        }
                    },
                    {
                        'cursor': 'OA==',
                        'node': {
                            'description': 'Cats 3',
                            'id': 'RGF0YXNldDpkZWZhdWx0JmRhdGFzZXQz',
                            'name': 'dataset3'
                        }
                    },
                    {
                        'cursor': 'OQ==',
                        'node': {
                            'description': 'Cats 2',
                            'id': 'RGF0YXNldDpkZWZhdWx0JmRhdGFzZXQy',
                            'name': 'dataset2'
                        }
                    }
                ],
                'pageInfo': {
                    'hasNextPage': False,
                    'hasPreviousPage': False
                }
            }
        }
    }
}

snapshots['TestDatasetQueries.test_pagination 1'] = {
    'data': {
        'datasetList': {
            'localDatasets': {
                'edges': [
                    {
                        'cursor': 'MA==',
                        'node': {
                            'description': 'Cats 1',
                            'name': 'dataset1'
                        }
                    },
                    {
                        'cursor': 'MQ==',
                        'node': {
                            'description': 'Cats 2',
                            'name': 'dataset2'
                        }
                    }
                ],
                'pageInfo': {
                    'hasNextPage': True,
                    'hasPreviousPage': False
                }
            }
        }
    }
}

snapshots['TestDatasetQueries.test_pagination 2'] = {
    'data': {
        'datasetList': {
            'localDatasets': {
                'edges': [
                    {
                        'cursor': 'Mg==',
                        'node': {
                            'description': 'Cats 3',
                            'name': 'dataset3'
                        }
                    },
                    {
                        'cursor': 'Mw==',
                        'node': {
                            'description': 'Cats 4',
                            'name': 'dataset4'
                        }
                    },
                    {
                        'cursor': 'NA==',
                        'node': {
                            'description': 'Cats 5',
                            'name': 'dataset5'
                        }
                    },
                    {
                        'cursor': 'NQ==',
                        'node': {
                            'description': 'Cats 6',
                            'name': 'dataset6'
                        }
                    },
                    {
                        'cursor': 'Ng==',
                        'node': {
                            'description': 'Cats 7',
                            'name': 'dataset7'
                        }
                    }
                ],
                'pageInfo': {
                    'hasNextPage': True,
                    'hasPreviousPage': False
                }
            }
        }
    }
}

snapshots['TestDatasetQueries.test_pagination 3'] = {
    'data': {
        'datasetList': {
            'localDatasets': {
                'edges': [
                    {
                        'cursor': 'Nw==',
                        'node': {
                            'description': 'Cats 8',
                            'name': 'dataset8'
                        }
                    },
                    {
                        'cursor': 'OA==',
                        'node': {
                            'description': 'Cats 9',
                            'name': 'dataset9'
                        }
                    },
                    {
                        'cursor': 'OQ==',
                        'node': {
                            'description': 'Cats other',
                            'name': 'dataset-other'
                        }
                    }
                ],
                'pageInfo': {
                    'hasNextPage': False,
                    'hasPreviousPage': False
                }
            }
        }
    }
}

snapshots['TestDatasetQueries.test_pagination 4'] = {
    'data': {
        'datasetList': {
            'localDatasets': {
                'edges': [
                ],
                'pageInfo': {
                    'hasNextPage': False,
                    'hasPreviousPage': False
                }
            }
        }
    }
}

snapshots['TestDatasetQueries.test_get_dataset_all_fields 1'] = {
    'data': {
        'dataset': {
            'activityRecords': {
                'edges': [
                    {
                        'node': {
                            'importance': 255,
                            'message': 'Created new Dataset: default/dataset8',
                            'show': True,
                            'tags': [
                            ],
                            'type': 'DATASET'
                        }
                    },
                    {
                        'node': {
                            'importance': 255,
                            'message': 'Updated Dataset storage backend configuration',
                            'show': True,
                            'tags': [
                                'config'
                            ],
                            'type': 'DATASET'
                        }
                    }
                ],
                'pageInfo': {
                    'hasNextPage': False,
                    'hasPreviousPage': False
                }
            },
            'datasetType': {
                'description': 'Dataset storage provided by your Gigantum account supporting files up to 5GB in size',
                'icon': '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',
                'id': 'RGF0YXNldFR5cGU6Z2lnYW50dW1fb2JqZWN0X3Yx',
                'name': 'Gigantum Cloud',
                'readme': '''Gigantum Cloud Datasets are backed by a scalable object storage service that is linked to
your Gigantum account and credentials. It provides efficient storage at the file level and works seamlessly with the
Client.

This dataset type is fully managed. That means as you modify data, each version will be tracked independently. Syncing
to Gigantum Cloud will count towards your storage quota and include all versions of files.
''',
                'storageType': 'gigantum_object_v1',
                'tags': [
                    'gigantum'
                ]
            },
            'description': 'Cats 8',
            'id': 'RGF0YXNldDpkZWZhdWx0JmRhdGFzZXQ4',
            'name': 'dataset8',
            'schemaVersion': 2
        }
    }
}
