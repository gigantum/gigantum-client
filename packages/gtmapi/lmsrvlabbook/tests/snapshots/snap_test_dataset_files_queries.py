# -*- coding: utf-8 -*-
# snapshottest: v1 - https://goo.gl/zC4yUc
from __future__ import unicode_literals

from snapshottest import Snapshot


snapshots = Snapshot()

snapshots['TestDatasetFilesQueries.test_get_dataset_files 1'] = {
    'data': {
        'dataset': {
            'allFiles': {
                'edges': [
                    {
                        'cursor': 'MA==',
                        'node': {
                            'isDir': True,
                            'isLocal': True,
                            'key': 'other_dir/',
                            'size': '0'
                        }
                    },
                    {
                        'cursor': 'MQ==',
                        'node': {
                            'isDir': False,
                            'isLocal': True,
                            'key': 'other_dir/test4.txt',
                            'size': '12'
                        }
                    },
                    {
                        'cursor': 'Mg==',
                        'node': {
                            'isDir': False,
                            'isLocal': True,
                            'key': 'other_dir/test5.txt',
                            'size': '9'
                        }
                    },
                    {
                        'cursor': 'Mw==',
                        'node': {
                            'isDir': False,
                            'isLocal': True,
                            'key': 'test1.txt',
                            'size': '8'
                        }
                    },
                    {
                        'cursor': 'NA==',
                        'node': {
                            'isDir': False,
                            'isLocal': True,
                            'key': 'test2.txt',
                            'size': '3'
                        }
                    },
                    {
                        'cursor': 'NQ==',
                        'node': {
                            'isDir': False,
                            'isLocal': True,
                            'key': 'test3.txt',
                            'size': '3'
                        }
                    }
                ],
                'pageInfo': {
                    'endCursor': 'NQ==',
                    'hasNextPage': False,
                    'hasPreviousPage': False
                }
            },
            'description': 'Cats 2',
            'id': 'RGF0YXNldDpkZWZhdWx0JnRlc3QtZGF0YXNldA==',
            'name': 'test-dataset'
        }
    }
}

snapshots['TestDatasetFilesQueries.test_get_dataset_files 2'] = {
    'data': {
        'dataset': {
            'allFiles': {
                'edges': [
                    {
                        'cursor': 'MA==',
                        'node': {
                            'isDir': True,
                            'isLocal': True,
                            'key': 'other_dir/',
                            'size': '0'
                        }
                    },
                    {
                        'cursor': 'MQ==',
                        'node': {
                            'isDir': False,
                            'isLocal': True,
                            'key': 'other_dir/test4.txt',
                            'size': '12'
                        }
                    }
                ],
                'pageInfo': {
                    'endCursor': 'MQ==',
                    'hasNextPage': True,
                    'hasPreviousPage': False
                }
            },
            'description': 'Cats 2',
            'id': 'RGF0YXNldDpkZWZhdWx0JnRlc3QtZGF0YXNldA==',
            'name': 'test-dataset'
        }
    }
}

snapshots['TestDatasetFilesQueries.test_get_dataset_files 3'] = {
    'data': {
        'dataset': {
            'allFiles': {
                'edges': [
                    {
                        'cursor': 'Mg==',
                        'node': {
                            'isDir': False,
                            'isLocal': True,
                            'key': 'other_dir/test5.txt',
                            'size': '9'
                        }
                    }
                ],
                'pageInfo': {
                    'endCursor': 'Mg==',
                    'hasNextPage': True,
                    'hasPreviousPage': True
                }
            },
            'description': 'Cats 2',
            'id': 'RGF0YXNldDpkZWZhdWx0JnRlc3QtZGF0YXNldA==',
            'name': 'test-dataset'
        }
    }
}

snapshots['TestDatasetFilesQueries.test_get_dataset_files 4'] = {
    'data': {
        'dataset': {
            'allFiles': {
                'edges': [
                    {
                        'cursor': 'Mg==',
                        'node': {
                            'isDir': False,
                            'isLocal': True,
                            'key': 'other_dir/test5.txt',
                            'size': '9'
                        }
                    },
                    {
                        'cursor': 'Mw==',
                        'node': {
                            'isDir': False,
                            'isLocal': True,
                            'key': 'test1.txt',
                            'size': '8'
                        }
                    },
                    {
                        'cursor': 'NA==',
                        'node': {
                            'isDir': False,
                            'isLocal': True,
                            'key': 'test2.txt',
                            'size': '3'
                        }
                    },
                    {
                        'cursor': 'NQ==',
                        'node': {
                            'isDir': False,
                            'isLocal': True,
                            'key': 'test3.txt',
                            'size': '3'
                        }
                    }
                ],
                'pageInfo': {
                    'endCursor': 'NQ==',
                    'hasNextPage': False,
                    'hasPreviousPage': True
                }
            },
            'description': 'Cats 2',
            'id': 'RGF0YXNldDpkZWZhdWx0JnRlc3QtZGF0YXNldA==',
            'name': 'test-dataset'
        }
    }
}

snapshots['TestDatasetFilesQueries.test_get_dataset_files_missing 1'] = {
    'data': {
        'dataset': {
            'allFiles': {
                'edges': [
                    {
                        'cursor': 'MA==',
                        'node': {
                            'isDir': True,
                            'isLocal': True,
                            'key': 'other_dir/',
                            'size': '0'
                        }
                    },
                    {
                        'cursor': 'MQ==',
                        'node': {
                            'isDir': False,
                            'isLocal': True,
                            'key': 'other_dir/test4.txt',
                            'size': '12'
                        }
                    },
                    {
                        'cursor': 'Mg==',
                        'node': {
                            'isDir': False,
                            'isLocal': True,
                            'key': 'other_dir/test5.txt',
                            'size': '9'
                        }
                    },
                    {
                        'cursor': 'Mw==',
                        'node': {
                            'isDir': False,
                            'isLocal': True,
                            'key': 'test1.txt',
                            'size': '8'
                        }
                    },
                    {
                        'cursor': 'NA==',
                        'node': {
                            'isDir': False,
                            'isLocal': True,
                            'key': 'test2.txt',
                            'size': '3'
                        }
                    },
                    {
                        'cursor': 'NQ==',
                        'node': {
                            'isDir': False,
                            'isLocal': True,
                            'key': 'test3.txt',
                            'size': '3'
                        }
                    }
                ],
                'pageInfo': {
                    'endCursor': 'NQ==',
                    'hasNextPage': False,
                    'hasPreviousPage': False
                }
            },
            'description': 'Cats 2',
            'id': 'RGF0YXNldDpkZWZhdWx0JnRlc3QtZGF0YXNldA==',
            'name': 'test-dataset'
        }
    }
}

snapshots['TestDatasetFilesQueries.test_get_dataset_files_missing 2'] = {
    'data': {
        'dataset': {
            'allFiles': {
                'edges': [
                    {
                        'cursor': 'MA==',
                        'node': {
                            'isDir': True,
                            'isLocal': True,
                            'key': 'other_dir/',
                            'size': '0'
                        }
                    },
                    {
                        'cursor': 'MQ==',
                        'node': {
                            'isDir': False,
                            'isLocal': True,
                            'key': 'other_dir/test4.txt',
                            'size': '12'
                        }
                    },
                    {
                        'cursor': 'Mg==',
                        'node': {
                            'isDir': False,
                            'isLocal': True,
                            'key': 'other_dir/test5.txt',
                            'size': '9'
                        }
                    },
                    {
                        'cursor': 'Mw==',
                        'node': {
                            'isDir': False,
                            'isLocal': False,
                            'key': 'test1.txt',
                            'size': '8'
                        }
                    },
                    {
                        'cursor': 'NA==',
                        'node': {
                            'isDir': False,
                            'isLocal': False,
                            'key': 'test2.txt',
                            'size': '3'
                        }
                    },
                    {
                        'cursor': 'NQ==',
                        'node': {
                            'isDir': False,
                            'isLocal': True,
                            'key': 'test3.txt',
                            'size': '3'
                        }
                    }
                ],
                'pageInfo': {
                    'endCursor': 'NQ==',
                    'hasNextPage': False,
                    'hasPreviousPage': False
                }
            },
            'description': 'Cats 2',
            'id': 'RGF0YXNldDpkZWZhdWx0JnRlc3QtZGF0YXNldA==',
            'name': 'test-dataset'
        }
    }
}
