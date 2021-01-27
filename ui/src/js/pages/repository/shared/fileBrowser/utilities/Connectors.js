// store
import store from 'JS/redux/store';
import {
  setWarningMessage,
} from 'JS/redux/actions/footer';
// utilities
import FileBrowserMutations from './FileBrowserMutations';
import prepareUpload from './PrepareUpload';

const dragSource = {

  canDrag(props) {
    // You can disallow drag based on props
    return !props.lockFileBrowser;
  },

  isDragging(props, monitor) {
    return monitor.getItem().key === props.key;
  },

  beginDrag(props) {
    return {
      isDragging: true,
      fileData: props.fileData,
      isLocal: props.isLocal,
      section: props.section,
    };
  },

  endDrag(props, monitor) {
    if (!monitor.didDrop()) {
      return;
    }
    const dropResult = monitor.getDropResult();
    const fileNameParts = props.fileData.edge.node.key.split('/');
    const fileName = fileNameParts[fileNameParts.length - 1];

    if (dropResult.fileData && !((props.section === 'data') && !dropResult.isLocal)) {
      const pathArray = dropResult.fileData.edge.node.key.split('/');
      // remove filename or empty string
      pathArray.pop();
      const path = pathArray.join('/');
      const newKey = path ? `${path}/${fileName}` : `${fileName}`;
      const newKeyArray = dropResult.fileData.edge.node.key.split('/');
      const fileKeyArray = props.fileData.edge.node.key.split('/');

      newKeyArray.pop();
      fileKeyArray.pop();

      let newKeyPath = newKeyArray.join('/');
      const fileKeyPath = fileKeyArray.join('/');
      newKeyPath = newKeyPath.replace(/\/\/\/g/, '/');
      const trimmedFilePath = (fileKeyPath + (fileName.length ? `/${fileName}` : '')).split('/').slice(0, -1).join('/');

      if ((newKeyPath !== fileKeyPath) && (trimmedFilePath !== newKeyPath)) {
        if (newKey !== props.fileData.edge.node.key) {
          const removeIds = [props.fileData.edge.node.id];
          const currentHead = props.fileData;
          // check if folder has children and push id into array to removed by optomistic updater
          const searchChildren = (parent) => {
            if (parent.children) {
              Object.keys(parent.children).forEach((childKey) => {
                if (parent.children[childKey].edge) {
                  removeIds.push(parent.children[childKey].edge.node.id);
                  searchChildren(parent.children[childKey]);
                }
              });
            }
          };

          searchChildren(currentHead);

          const moveLabbookFileData = {
            newKey,
            edge: props.fileData.edge,
            removeIds,
          };

          if (props.mutations) {
            if (props.section !== 'data') {
              props.mutations.moveLabbookFile(moveLabbookFileData, () => {});
            } else {
              props.mutations.moveDatasetFile(moveLabbookFileData, () => {});
            }
          } else {
            const {
              parentId,
              connection,
              section,
              owner,
              name,
            } = props;
            const mutationData = {
              owner,
              name,
              parentId,
              connection,
              section,
            };

            const mutations = new FileBrowserMutations(mutationData);
            if (section !== 'data') {
              mutations.moveLabbookFile(moveLabbookFileData, (response) => {});
            } else {
              mutations.moveLDatasetFile(moveLabbookFileData, (response) => {});
            }
          }
        }
      }
    }
  },
};

function dragCollect(connect, monitor) {
  return {
    connectDragPreview: connect.dragPreview(),
    connectDragSource: connect.dragSource(),
    isDragging: monitor.sourceId === monitor.getSourceId(),
  };
}

const targetSource = {
  canDrop(props, monitor) {
    const item = monitor.getItem();
    const { uploading } = store.getState().fileBrowser;
    const mouseoverAllowed = !uploading
      && (!((props.section === 'data') && !item.isLocal)
      || (!item.fileData));
    if (props
      && props.fileData && item.fileData
      && props.fileData.edge && item.fileData.edge
      && props.fileData.edge.node && item.fileData.edge.node
      && props.fileData.edge.node.key.startsWith(item.fileData.edge.node.key)
    ) {
      return false;
    }
    return monitor.isOver({ shallow: true }) && mouseoverAllowed && !props.lockFileBrowser;
  },
  drop(props, monitor, component) {
    // TODO: clean up this code, some of this logic is being duplicated. make better use of functions
    const dndItem = monitor.getItem();
    const { section } = props.section ? props : props.mutationData;
    if ((section === 'data') && !props.uploadAllowed) {
      setWarningMessage(props.owner, props.name, 'You do not have adequate permissions to modify this dataset');
      return;
    }
    const promptType = props.section
      ? props.section
      : ((props.mutationData) && (props.mutationData.section))
        ? props.mutationData.section
        : '';
    let newPath;
    let fileKey;
    // non root folder drop
    if (dndItem && props.fileData) {
      if (!dndItem.dirContent) {
        fileKey = props.fileData.edge.node.key;

        const fileNameParts = fileKey.split('/');
        const fileName = fileNameParts[fileNameParts.length - 1];
        const newKey = props.newKey || props.fileKey;
        newPath = newKey + fileName;
        fileKey = props.fileKey;
      } else {
        prepareUpload(dndItem, props, monitor, props.mutationData, component);
      }
    } else {
      // root folder upload
      const {
        parentId,
        connection,
        section,
        owner,
        name,
      } = props;

      const mutationData = {
        owner,
        name,
        parentId,
        connection,
        section,
      };
      // uploads to root directory
      const item = monitor.getItem();
      // check to see if it is an upload
      if (item.files) {
        prepareUpload(item, props, monitor, component.state.mutationData, component);
      } else { // else it's a move
        const dropResult = monitor.getDropResult();
        const currentKey = item.fileData.edge.node.key;
        const splitKey = currentKey.split('/');
        const newKeyTemp = (splitKey[splitKey.length - 1] !== '') ? splitKey[splitKey.length - 1] : splitKey[splitKey.length - 2];
        const splitFolder = dropResult && dropResult.fileData ? dropResult.fileData.edge.node.key.split('/') : [''];
        if (splitFolder !== '') {
          splitFolder.pop();
        }

        const dropFolderKey = splitFolder.join('/');

        let newKey = item.fileData && item.fileData.edge.node.isDir ? `${dropFolderKey}/${newKeyTemp}/` : `${dropFolderKey}/${newKeyTemp}`;
        newKey = dropResult && dropResult.fileData ? newKey : `${newKeyTemp}`;

        if ((newKey !== item.fileData.edge.node.key) && ((`${newKey}/`) !== item.fileData.edge.node.key)) {
          const removeIds = [item.fileData.edge.node.id];
          const currentHead = item.fileData;

          const searchChildren = (parent) => {
            if (parent.children) {
              Object.keys(parent.children).forEach((childKey) => {
                if (parent.children[childKey].edge) {
                  removeIds.push(parent.children[childKey].edge.node.id);
                  searchChildren(parent.children[childKey]);
                }
              });
            }
          };

          searchChildren(currentHead);
          const moveLabbookFileData = {
            newKey,
            edge: item.fileData.edge,
            removeIds,
          };

          if (props.mutations) {
            if (props.section !== 'data') {
              props.mutations.moveLabbookFile(moveLabbookFileData, (response) => {});
            } else {
              props.mutations.moveDatasetFile(moveLabbookFileData, (response) => {});
            }
          } else {
            const {
              parentId,
              connection,
              section,
              owner,
              name,
            } = props;

            const mutationData = {
              owner,
              name,
              parentId,
              connection,
              section,
            };

            const mutations = new FileBrowserMutations(mutationData);

            if (props.section !== 'data') {
              mutations.moveLabbookFile(moveLabbookFileData, (response) => {});
            } else {
              mutations.moveDatasetFile(moveLabbookFileData, (response) => {});
            }
          }
        }
      }
    }

    return {
      fileData: props.fileData,
      isLocal: props.isLocal,
    };
  },
};

function targetCollect(connect, monitor) {
  // TODO: clean up this code, removal of file drop containers removes the need for some of this logic.
  // decide if drop zone should appear;
  const item = monitor.getItem();
  const currentTargetId = monitor.targetId;
  const isOverCurrent = monitor.isOver({ shallow: true });
  let isOver = monitor.isOver({});
  let canDrop = monitor.canDrop();
  let newLastTarget;
  // get a list of drop target ids
  const targetIds = monitor.internalMonitor.getTargetIds();
  const targets = targetIds.map(id => monitor.internalMonitor.registry.dropTargets.get(id));
  // if targets found
  if (targets.length > 0) {
    // get the last target
    const lastTarget = targets[targets.length - 1];

    // if last target is a file remove it
    if (lastTarget.props.fileData && !lastTarget.props.fileData.edge.node.isDir) {
      targets.pop();
    }
    newLastTarget = targets[targets.length - 1];
    // check if current targe is over last target
    isOver = (currentTargetId === newLastTarget.monitor.targetId) && canDrop;
  } else {
    isOver = false;
  }
  // check if item is dragging
  let dragItem;
  monitor.internalMonitor.registry.dragSources.forEach((item) => {
    if (item.ref && item.ref.current && item.ref.current.props.isDragging) {
      dragItem = item.ref.current;
    }
  });
  // compare dragItem and lastTarget
  if (dragItem && newLastTarget) {
    const dragKeyArray = dragItem.props.fileData.edge.node.key.split('/');
    dragKeyArray.pop();
    // check if file drag key is the same
    const dragKeyPruned = dragKeyArray.join('/') === '' ? '' : `${dragKeyArray.join('/')}/`;
    const dropKey = newLastTarget.props.files ? '' : newLastTarget.props.fileData.edge.node.key;
    canDrop = (dragKeyPruned !== dropKey);
    isOver = isOver && canDrop;
  }
  const { uploading } = store.getState().fileBrowser;
  isOver = isOver && !uploading;
  if (item && ((item.section === 'data') && !item.isLocal)) {
    // empty object expected for collect
    return {};
  }
  return {
    connectDropTarget: connect.dropTarget(),
    canDrop,
    isOver,
    isOverCurrent,
  };
}

const Connectors = {
  dragSource,
  dragCollect,
  targetSource,
  targetCollect,
};

export default Connectors;
