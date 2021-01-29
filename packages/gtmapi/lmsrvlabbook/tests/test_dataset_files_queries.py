import pytest
import os
from snapshottest import snapshot
from lmsrvlabbook.tests.fixtures import fixture_single_dataset


class TestDatasetFilesQueries(object):
    def test_get_dataset_files(self, fixture_single_dataset, snapshot):
        query = """{
                    dataset(name: "test-dataset", owner: "default") {
                      id
                      name
                      description
                      allFiles {
                        edges{
                            node {
                              key
                              isDir
                              isLocal
                              size
                            }
                            cursor
                        }
                        pageInfo{
                          hasNextPage
                          hasPreviousPage
                          endCursor
                        }
                      }
                    }
                    }
                """
        r = fixture_single_dataset[2].execute(query)
        assert 'errors' not in r
        snapshot.assert_match(r)

        query = """{
                           dataset(name: "test-dataset", owner: "default") {
                             id
                             name
                             description
                             allFiles(first: 2) {
                               edges{
                                   node {
                                     key
                                     isDir
                                     isLocal
                                     size
                                   }
                                   cursor
                               }
                               pageInfo{
                                 hasNextPage
                                 hasPreviousPage
                                 endCursor
                               }
                             }
                           }
                           }
                       """
        r = fixture_single_dataset[2].execute(query)
        assert 'errors' not in r
        snapshot.assert_match(r)

        query = """{
                       dataset(name: "test-dataset", owner: "default") {
                         id
                         name
                         description
                         allFiles(first: 1, after: "MQ==") {
                           edges{
                               node {
                                 key
                                 isDir
                                 isLocal
                                 size
                               }
                               cursor
                           }
                           pageInfo{
                             hasNextPage
                             hasPreviousPage
                             endCursor
                           }
                         }
                       }
                       }
                   """
        r = fixture_single_dataset[2].execute(query)
        assert 'errors' not in r
        snapshot.assert_match(r)

        query = """{
                       dataset(name: "test-dataset", owner: "default") {
                         id
                         name
                         description
                         allFiles(first: 100, after: "MQ==") {
                           edges{
                               node {
                                 key
                                 isDir
                                 isLocal
                                 size
                               }
                               cursor
                           }
                           pageInfo{
                             hasNextPage
                             hasPreviousPage
                             endCursor
                           }
                         }
                       }
                       }
                   """
        r = fixture_single_dataset[2].execute(query)
        assert 'errors' not in r
        snapshot.assert_match(r)

    def test_get_dataset_files_missing(self, fixture_single_dataset, snapshot):
        query = """{
                    dataset(name: "test-dataset", owner: "default") {
                      id
                      name
                      description
                      allFiles {
                        edges{
                            node {
                              key
                              isDir
                              isLocal
                              size
                            }
                            cursor
                        }
                        pageInfo{
                          hasNextPage
                          hasPreviousPage
                          endCursor
                        }
                      }
                    }
                    }
                """
        r = fixture_single_dataset[2].execute(query)
        assert 'errors' not in r
        snapshot.assert_match(r)

        ds = fixture_single_dataset[3]
        cache_mgr = fixture_single_dataset[4]
        revision = ds.git.repo.head.commit.hexsha
        os.remove(os.path.join(cache_mgr.cache_root, revision, 'test1.txt'))
        os.remove(os.path.join(cache_mgr.cache_root, revision, 'test2.txt'))

        query = """{
                    dataset(name: "test-dataset", owner: "default") {
                      id
                      name
                      description
                      allFiles {
                        edges{
                            node {
                              key
                              isDir
                              isLocal
                              size
                            }
                            cursor
                        }
                        pageInfo{
                          hasNextPage
                          hasPreviousPage
                          endCursor
                        }
                      }
                    }
                    }
                """
        r = fixture_single_dataset[2].execute(query)
        assert 'errors' not in r
        snapshot.assert_match(r)
