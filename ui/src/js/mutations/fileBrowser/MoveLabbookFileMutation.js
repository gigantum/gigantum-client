// vendor
import {
  commitMutation,
  graphql,
} from 'react-relay';
import RelayRuntime from 'relay-runtime';
import uuidv4 from 'uuid/v4';
// environment
import environment from 'JS/createRelayEnvironment';
// redux
import { setErrorMessage } from 'JS/redux/actions/footer';

const mutation = graphql`
  mutation MoveLabbookFileMutation($input: MoveLabbookFileInput!){
    moveLabbookFile(input: $input){
      updatedEdges{
        node{
            id
            isDir
            modifiedAt
            key
            size
          }
          cursor
      }
      clientMutationId
    }
  }
`;

function sharedDeleteUpdater(store, labbookID, removeIds, connectionKey) {
  const labbookProxy = store.get(labbookID);
  if (labbookProxy) {
    removeIds.forEach((deletedID) => {
      const conn = RelayRuntime.ConnectionHandler.getConnection(
        labbookProxy,
        connectionKey,
      );

      if (conn) {
        RelayRuntime.ConnectionHandler.deleteNode(
          conn,
          deletedID,
        );
        store.delete(deletedID);
      }
    });
  }
}


export default function MoveLabbookFileMutation(
  connectionKey,
  owner,
  labbookName,
  labbookId,
  edge,
  srcPath,
  dstPath,
  section,
  removeIds,
  callback,
) {
  const variables = {
    input: {
      owner,
      labbookName,
      srcPath,
      dstPath,
      section,
      clientMutationId: uuidv4(),
    },
  };

  const configs = [{
    type: 'RANGE_ADD',
    parentID: labbookId,
    connectionInfo: [{
      key: connectionKey,
      rangeBehavior: 'append',
    }],
    edgeName: 'newLabbookFileEdge',
  }];

  if (removeIds && removeIds.length) {
    removeIds.forEach((id) => {
      configs.unshift({
        type: 'NODE_DELETE',
        deletedIDFieldName: id,
      });
    });
  }

  commitMutation(
    environment,
    {
      mutation,
      variables,
      onCompleted: (response, error) => {
        if (error) {
          console.log(error);
          setErrorMessage(owner, labbookName, `ERROR: Could not Move labbook file ${srcPath}`, error);
        }
        callback(response, error);
      },
      onError: err => console.error(err),
      optimisticUpdater: (store) => {
        const labbookProxy = store.get(labbookId);

        if (labbookProxy && (edge.node !== null)) {
          const conn = RelayRuntime.ConnectionHandler.getConnection(
            labbookProxy,
            connectionKey,
          );

          const node = store.get(edge.node.id);
          node.setValue(edge.node.id, 'id');
          node.setValue(edge.node.isDir, 'isDir');
          node.setValue(dstPath, 'key');
          node.setValue(edge.node.modifiedAt, 'modifiedAt');
          node.setValue(edge.node.size, 'size');

          if (!store.get(edge.node.id)) {
            const newEdge = RelayRuntime.ConnectionHandler.createEdge(
              store,
              conn,
              node,
              'newLabbookFileEdge',
            );
            RelayRuntime.ConnectionHandler.insertEdgeAfter(
              conn,
              newEdge,
              edge.cursor,
            );
          }
        }
      },
      updater: (store, response) => {
        sharedDeleteUpdater(store, labbookId, removeIds, connectionKey);
        if (response && response.moveLabbookFile && response.moveLabbookFile.updatedEdges) {
          response.moveLabbookFile.updatedEdges.forEach((labbookEdge) => {
            const labbookProxy = store.get(labbookId);

            if (labbookProxy && (labbookEdge.node !== null)) {
              const conn = RelayRuntime.ConnectionHandler.getConnection(
                labbookProxy,
                connectionKey,
              );
              const node = store.get(labbookEdge.node.id) ? store.get(labbookEdge.node.id) : store.create(labbookEdge.node.id, 'LabbookFile');

              node.setValue(labbookEdge.node.id, 'id');
              node.setValue(labbookEdge.node.isDir, 'isDir');
              node.setValue(labbookEdge.node.key, 'key');
              node.setValue(labbookEdge.node.modifiedAt, 'modifiedAt');
              node.setValue(labbookEdge.node.size, 'size');
              const newEdge = RelayRuntime.ConnectionHandler.createEdge(
                store,
                conn,
                node,
                'newLabbookFileEdge',
              );
              RelayRuntime.ConnectionHandler.insertEdgeAfter(
                conn,
                newEdge,
                labbookEdge.cursor,
              );
            }
          });
        }
      },

    },
  );
}
