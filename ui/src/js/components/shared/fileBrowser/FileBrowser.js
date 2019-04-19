// vendor
import React, { Component } from 'react';
import store from 'JS/redux/store';
import { DropTarget } from 'react-dnd';
import { NativeTypes } from 'react-dnd-html5-backend';
import classNames from 'classnames';
import shallowCompare from 'react-addons-shallow-compare'; // ES6
// assets
import './FileBrowser.scss';
// components
import Modal from 'Components/common/Modal';
import LinkModal from './LinkModal';
import File from './fileRow/File';
import Folder from './fileRow/Folder';
import Dataset from './fileRow/dataset/Dataset';
import AddSubfolder from './fileRow/AddSubfolder';
// util
import FileBrowserMutations from './utilities/FileBrowserMutations';
import Connectors from './utilities/Connectors';
import FileFormatter, { fileHandler } from './utilities/FileFormatter';


const checkLocalAll = (files) => {
  let isLocal = true;
  Object.keys(files).forEach((fileKey) => {
    if (files[fileKey].children) {
      const isChildrenLocal = checkLocalAll(files[fileKey].children);
      if (isChildrenLocal === false) {
        isLocal = false;
      }
    } else if (!files[fileKey].edge.node.isLocal) {
      isLocal = false;
    }
  });
  return isLocal;
};


const checkLocalIndividual = (files) => {
  let isLocal = true;
  const searchChildren = (parent) => {
    if (parent.children) {
      Object.keys(parent.children).forEach((childKey) => {
        if (parent.children[childKey].edge) {
          if (parent.children[childKey].edge.node.isLocal === false) {
            isLocal = false;
          }
          searchChildren(parent.children[childKey]);
        }
      });
    }
  };

  if (files.children) {
    searchChildren(files);
  } else {
    isLocal = files.edge.node.isLocal;
  }

  return isLocal;
};

class FileBrowser extends Component {
  constructor(props) {
    super(props);

    this.state = {
      mutations: new FileBrowserMutations(this._getMutationData()),
      mutationData: this._getMutationData(),
      hoverId: '',
      childrenState: {},
      multiSelect: 'none',
      search: '',
      isOverChildFile: false,
      sort: 'az',
      reverse: false,
      count: 0,
      files: {},
      aboveSize: window.innerWidth > 1240,
      popupVisible: false,
      fileSizePromptVisible: false,
      showLinkModal: false,
      downloadingAll: false,
    };

    this._deleteSelectedFiles = this._deleteSelectedFiles.bind(this);
    this._setState = this._setState.bind(this);
    this._updateChildState = this._updateChildState.bind(this);
    this._checkChildState = this._checkChildState.bind(this);
    this._updateDropZone = this._updateDropZone.bind(this);
    this._userAcceptsUpload = this._userAcceptsUpload.bind(this);
    this._userRejectsUpload = this._userRejectsUpload.bind(this);
    this._codeFilesUpload = this._codeFilesUpload.bind(this);
    this._codeDirUpload = this._codeDirUpload.bind(this);
  }

  static getDerivedStateFromProps(props, state) {
    const previousCount = state.count;
    const count = props.files.edges.length;
    const childrenState = {};


    const files = props.files.edges;

    const processChildState = (edges, datasetName) => {
      if (datasetName && edges.length === 0) {
        const adjustedKey = `${datasetName}/`;
        childrenState[adjustedKey] = {
          isSelected: (state.childrenState && state.childrenState[adjustedKey]) ? state.childrenState[adjustedKey].isSelected : false,
          isIncomplete: (state.childrenState && state.childrenState[adjustedKey]) ? state.childrenState[adjustedKey].isIncomplete : false,
          isExpanded: (state.childrenState && state.childrenState[adjustedKey]) ? state.childrenState[adjustedKey].isExpanded : false,
          isAddingFolder: (state.childrenState && state.childrenState[adjustedKey]) ? state.childrenState[adjustedKey].isAddingFolder : false,
        };
      }
      edges.forEach((edge) => {
        if (edge.node && edge.node.key) {
          const key = datasetName ? `${datasetName}/${edge.node.key}` : edge.node.key;
          const splitKey = key.split('/').filter(n => n);
          splitKey.forEach((key, index) => {
            if (index !== splitKey.length) {
              const tempKey = `${splitKey.slice(0, index).join('/')}/`;
              if (!childrenState[tempKey] && tempKey !== '/') {
                childrenState[tempKey] = {
                  isSelected: (state.childrenState && state.childrenState[tempKey]) ? state.childrenState[tempKey].isSelected : false,
                  isIncomplete: (state.childrenState && state.childrenState[tempKey]) ? state.childrenState[tempKey].isIncomplete : false,
                  isExpanded: (state.childrenState && state.childrenState[tempKey]) ? state.childrenState[tempKey].isExpanded : false,
                  isAddingFolder: (state.childrenState && state.childrenState[tempKey]) ? state.childrenState[tempKey].isAddingFolder : false,
                  edge: {
                    node: {
                      isDir: true,
                      isFavorite: false,
                      key: tempKey,
                      modifiedAt: Math.floor(Date.now() / 1000),
                      id: tempKey,
                    },
                  },
                };
              }
            }
          });

          const isSelected = (state.childrenState && state.childrenState[key])
            ? state.childrenState[key].isSelected
            : false;
          const isIncomplete = (state.childrenState && state.childrenState[key])
            ? state.childrenState[key].isIncomplete
            : false;
          const isExpanded = (state.childrenState && state.childrenState[key])
            ? state.childrenState[key].isExpanded
            : false;
          const isAddingFolder = (state.childrenState && state.childrenState[key])
            ? state.childrenState[key].isAddingFolder
            : false;
          childrenState[key] = {
            isSelected,
            isIncomplete,
            isExpanded,
            isAddingFolder,
            edge,
          };
        }
      });
    };

    processChildState(files);

    if (props.linkedDatasets) {
      props.linkedDatasets.forEach(
        dataset => processChildState(dataset.allFiles.edges, dataset.name),
      );
    }

    return {
      ...state,
      childrenState,
      search: count === previousCount ? state.search : '',
      count,
    };
  }

  /**
      sets worker
    */
  componentDidMount() {
    const { props, state } = this;
    const files = props.files.edges;
    const { linkedDatasets } = props;

    this.fileHandler = new FileFormatter(fileHandler);
    this.fileHandler.postMessage({
      files,
      search:
      state.search,
      linkedDatasets,
    });

    this.fileHandler.addEventListener('message', (evt) => {
      // has to be this, will only keep original state otherwise;
      const { fileHash } = this.state;

      if (fileHash !== evt.data.hash) {
        this.setState({
          fileHash: evt.data.hash,
          files: evt.data.files,
        });
      }
    });
  }

  shouldComponentUpdate(nextProps, nextState) {
    return shallowCompare(this, nextProps, nextState);
  }

  /*
      resets search
    */
  componentDidUpdate() {
    const { props, state } = this;
    if (this.list) {
      this.list.recomputeGridSize();
    }
    // TODO should not be using document to clear value
    const element = document.getElementsByClassName('FileBrowser__input')[0];
    if (state.search === '' && element && element.value !== '') {
      element.value = '';
    }
    const files = props.files.edges;
    const { linkedDatasets } = props;

    this.fileHandler.postMessage({
      files,
      linkedDatasets,
      search: state.search,
    });
  }

  /**
    *  @param {Boolean} allFilesLocal
    *  handles downloading all files in data-filebrowser
    *  @return {}
    */
  _handleDownloadAll(allFilesLocal) {
    if (!this.state.downloadingAll && !allFilesLocal) {
      const { owner, labbookName } = store.getState().routes;
      const data = {
        owner,
        datasetName: labbookName,
        allKeys: true,
      };
      data.successCall = () => {
        this.setState({ downloadingAll: false });
      };
      data.failureCall = () => {
        this.setState({ downloadingAll: false });
      };

      const callback = (response, error) => {
        if (error) {
          this.setState({ downloadingAll: false });
        }
      };
      this.setState({ downloadingAll: true });
      this.state.mutations.downloadDatasetFiles(data, callback);
    }
  }

  /**
    *  @param {string} key - key of file to be updated
    *  @param {boolean} isSelected - update if the value is selected
    *  @param {boolean} isIncomplete - update if the value is incomplete
    *  @param {boolean} isExpanded - update if the value is incomplete
    *  @param {boolean} isAddingFolder - update if the value is incomplete
    *  @return {}
    */
  _updateChildState(key, isSelected, isIncomplete, isExpanded, isAddingFolder) {
    let isChildSelected = false;
    let count = 0;
    let selectedCount = 0;
    const { childrenState } = this.state;
    childrenState[key].isSelected = isSelected;
    childrenState[key].isIncomplete = isIncomplete;
    childrenState[key].isExpanded = isExpanded;
    childrenState[key].isAddingFolder = isAddingFolder;

    for (const key in childrenState) {
      if (childrenState[key]) {
        if (childrenState[key].isSelected) {
          isChildSelected = true;
          selectedCount++;
        }
        count++;
      }
    }

    let multiSelect = !isChildSelected ? 'none' : (selectedCount === count) ? 'all' : 'partial';

    this.setState({ childrenState, multiSelect });
  }

  /**
    *  @param {string} stateKey
    *  @param {string || boolean || number} value
    *  update state of component for a given key value pair
    *  @return {}
    */
  _setState(key, value) {
    this.setState({ [key]: value });
  }

  /**
  *  @param {}
  *  sorts files into an object for rendering
  *  @return {object}
  */
  _getMutationData() {
    const {
      parentId,
      connection,
      favoriteConnection,
      section,
    } = this.props;
    const { owner, labbookName } = store.getState().routes;

    return {
      owner,
      labbookName,
      parentId,
      connection,
      favoriteConnection,
      section,
    };
  }

  /**
  *  @param {boolean} popupVisible
  *  triggers favoirte unfavorite mutation
  *  @return {}
  */
  _togglePopup(popupVisible) {
    this.setState({ popupVisible });
  }

  /**
  *  @param {}
  *  loops through selcted files and deletes them
  *  @return {}
  */
  _deleteSelectedFiles() {
    const self = this;
    const filePaths = [];
    const dirList = [];
    const comparePaths = [];
    const edges = [];
    const deletedKeys = [];

    for (const key in this.state.childrenState) {
      if (this.state.childrenState[key].isSelected) {
        const { edge } = this.state.childrenState[key];
        delete this.state.childrenState[key];
        edge.node.isDir && deletedKeys.push(key);
        comparePaths.push(edge.node.key);
        filePaths.push(edge.node.key);
        edges.push(edge);
        if (edge.node.isDir) {
          dirList.push(edge.node.key);
        }
      }
    }
    Object.keys(this.state.childrenState).forEach((key) => {
      deletedKeys.forEach((deletedKey) => {
        if (key.startsWith(deletedKey) && this.state.childrenState[key]) {
          const { edge } = this.state.childrenState[key];
          delete this.state.childrenState[key];
          comparePaths.push(edge.node.key);
          filePaths.push(edge.node.key);
          edges.push(edge);
          if (edge.node.isDir) {
            dirList.push(edge.node.key);
          }
        }
      });
    });

    const filteredPaths = filePaths.filter((key) => {
      let folderKey = key.substr(0, key.lastIndexOf('/'));
      folderKey = `${folderKey}/`;

      const hasDir = dirList.some(dir => ((key.indexOf(dir) > -1) && (dir !== key)));
      return !hasDir;
    });
    self._togglePopup(false);
    self._deleteMutation(filteredPaths, edges);
  }

  /**
  *  @param {}
  *  selects all or unselects files
  *  @return {}
  */
  _selectFiles() {
    const { state } = this;
    let isSelected = false;
    let count = 0;
    let selectedCount = 0;

    for (const key in state.childrenState) {
      if (state.childrenState[key]) {
        if (state.childrenState[key].isSelected) {
          isSelected = true;
          selectedCount++;
        }
        count++;
      }
    }
    const multiSelect = (count === selectedCount) ? 'none' : 'all';
    const { childrenState } = this.state;

    for (const key in childrenState) {
      if (childrenState[key]) {
        childrenState[key].isSelected = (multiSelect === 'all');
        count++;
      }
    }
    this.setState({
      multiSelect,
      childrenState,
    });
  }

  /**
  *  @param {Array:[string]} filePaths
  *  @param {Array:[Object]} edges
  *  triggers delete muatation
  *  @return {}
  */
  _deleteMutation(filePaths, edges) {
    const { state } = this;
    const data = {
      filePaths,
      edges,
    };
    this.setState({ multiSelect: 'none' });
    state.mutations.deleteLabbookFiles(data, () => {});
  }

  /**
  *  @param {string} key
  *  @param {boolean} value
  *  updates boolean state of a given key
  *  @return {}
  */
  _updateStateBoolean(key, value) {
    this.setState({ [key]: value });
  }

  /**
  *  @param {}
  *  checks if folder refs has props.isOver === true
  *  @return {boolean} isSelected - returns true if a child has been selected
  */
  _checkChildState() {
    const { state } = this;
    const keys = Object.keys(state.childrenState);
    let isSelected = false;

    keys.forEach((key) => {
      if (state.childrenState[key].isSelected) {
        isSelected = true;
      }
    });

    return { isSelected };
  }

  /**
  *  @param {evt}
  *  update state
  *  @return {}
  */
  _updateSearchState(evt) {
    this.setState({ search: evt.target.value });
  }

  /**
  *  @param {boolean} isOverChildFile
  *  update state to update drop zone
  *  @return {}
  */
  _updateDropZone(isOverChildFile) {
    this.setState({ isOverChildFile });
  }

  /**
  *  @param {Array:[Object]} array
  *  @param {string} type
  *  @param {boolean} reverse
  *  @param {Object} children
  *  @param {string} section
  *  returns sorted children
  *  @return {}
  */
  _childSort(array, type, reverse, children, section) {
    const { props } = this;
    array.sort((a, b) => {
      const isAUntracked = (a === 'untracked') && (section === 'folder') && (props.section === 'output');
      const isBUntracked = (b === 'untracked') && (section === 'folder') && (props.section === 'output');
      let newIndex = isAUntracked ? -1 : 0;
      newIndex = isBUntracked ? 1 : newIndex;
      let lowerA;
      let lowerB;

      if ((type === 'az') || ((type === 'size') && (section === 'folder'))) {
        lowerA = a.toLowerCase();
        lowerB = b.toLowerCase();

        if ((type === 'size') || !reverse) {
          newIndex = (lowerA < lowerB) ? -1 : newIndex;
          newIndex = (lowerA > lowerB) ? 1 : newIndex;
          return newIndex;
        }

        newIndex = (lowerA < lowerB) ? 1 : newIndex;
        newIndex = (lowerA > lowerB) ? -1 : newIndex;
        return newIndex;
      } if (type === 'modified') {
        lowerA = children[a].edge.node.modifiedAt;
        lowerB = children[b].edge.node.modifiedAt;

        if (!reverse) {
          newIndex = (lowerA < lowerB) ? -1 : newIndex;
          newIndex = (lowerA > lowerB) ? 1 : newIndex;
          return newIndex;
        }

        newIndex = (lowerA < lowerB) ? 1 : newIndex;
        newIndex = (lowerA > lowerB) ? -1 : newIndex;
        return newIndex;
      } if (type === 'size') {
        lowerA = children[a].edge.node.size;
        lowerB = children[b].edge.node.size;
        if (!reverse) {
          newIndex = (lowerA < lowerB) ? -1 : newIndex;
          newIndex = (lowerA > lowerB) ? 1 : newIndex;
          return newIndex;
        }
        newIndex = (lowerA < lowerB) ? 1 : newIndex;
        newIndex = (lowerA > lowerB) ? -1 : newIndex;
        return newIndex;
      }
      return 0;
    });
    return array;
  }

  /**
  *  @param {String} Type
  *  handles state changes for type
  *  @return {}
  */
  _handleSort(type) {
    const { state } = this;
    if (type === state.sort) {
      this.setState((prevState) => {
        const reverse = !prevState.reverse;
        return { reverse };
      });
    } else {
      this.setState({ sort: type, reverse: false });
    }
  }

  /**
  *  @param {}
  *  show modal to prompt user to continue upload or not
  *  @return {}
  */
  _promptUserToAcceptUpload() {
    this.setState({ fileSizePromptVisible: true });
  }

  /**
  *  @param {object} dndItem - prop passed from react dnd that contains files and dirContent
  *  @param {object} props - props from the component triggering the upload process
  *  @param {object} mutationData - mutation data from the component triggering the upload process
  *  @param {object} uploadDirContent - function in Connectors.js that will kick off the upload
  *                                     process once the users decision has been made
  *  @param {object} fileSizeData - object with 2 arrays, fileSizeNotAllowed files that are too big
  *                                 for the code section, fileSizePrompt files that are between 10MB
  *                                 and 100MB and require the user to confirm
  *  set computed connector data into state to be triggered after user makes its decision
  *  show modal to prompt user to continue upload or not
  *  @return {}
  */
  _codeDirUpload(dndItem, props, mutationData, uploadDirContent, fileSizeData) {
    this.setState({
      uploadData: {
        type: 'dir',
        dndItem,
        props,
        mutationData,
        uploadDirContent,
        fileSizeData,
      },
    });

    this._promptUserToAcceptUpload();
  }

  /**
  *  @param {object} files - list of files to be uploaded
  *  @param {object} props - props from the component triggering the upload process
  *  @param {object} mutationData - mutation data from the component
  *                                 triggering the upload process
  *  @param {object} createFiles - function in Connectors.js that will kick off
  *                                the upload process once the users decision has been made
  *  @param {object} fileSizeData - object with 2 arrays, fileSizeNotAllowed files that
  *                                 are too big for the code section, fileSizePrompt files that
  *                                 are between 10MB and 100MB and require the user to confirm
  *  set computed connector data into state to be triggered after user makes its decision
  *  show modal to prompt user to continue upload or not
  *  @return {}
  */
  _codeFilesUpload(files, props, mutationData, createFiles, fileSizeData) {
    this.setState({
      uploadData: {
        type: 'files',
        files,
        mutationData,
        props,
        createFiles,
        fileSizeData,
      },
    });

    this._promptUserToAcceptUpload();
  }

  /**
  *  @param {}
  *  creates a file using AddLabbookFileMutation by passing a blob
  *  set state of user prompt modal
  */
  _userAcceptsUpload() {
    const { state } = this;
    const { fileSizeData } = state.uploadData;

    if (state.uploadData.type === 'dir') {
      const {
        uploadDirContent,
        dndItem,
        props,
        mutationData,
      } = state.uploadData;

      uploadDirContent(dndItem, props, mutationData, fileSizeData);
    } else {
      const {
        item,
        component,
        props,
      } = state.uploadData;

      createFiles(item.files, '', component.state.mutationData, props, fileSizeData);
    }

    this.setState({ fileSizePromptVisible: false });
  }

  /**
  *  @param {}
  *  creates a file using AddLabbookFileMutation by passing a blob
  *  set state of user prompt modal
  */
  _userRejectsUpload() {
    const { state } = this;
    const {
      files,
      prefix,
    } = state.uploadData;
    const fileSizeData = this.state.uploadData.fileSizeData;
    const fileSizeNotAllowed = fileSizeData.fileSizeNotAllowed.concat(fileSizeData.fileSizePrompt);

    fileSizeData.fileSizeNotAllowed = fileSizeNotAllowed;

    if (state.uploadData.type === 'dir') {
      const {
        uploadDirContent,
        dndItem,
        props,
        mutationData,
        fileSizeData,
      } = state.uploadData;

      uploadDirContent(dndItem, props, mutationData, fileSizeData);
    } else {
      const {
        item,
        component,
        props,
        fileSizeData,
      } = state.uploadData;

      createFiles(item.files, '', component.state.mutationData, props, fileSizeData);
    }

    this.setState({ fileSizePromptVisible: false });
  }

  /**
  *  @param {}
  *  user cancels upload
  */
  _cancelUpload() {
    this.setState({ fileSizePromptVisible: false });
  }

  /**
  *  @param {}
  *  gets file prompt text individual sections
  *  @return {string}
  */
  _getFilePromptText() {
    const { props } = this;
    const upperFirstLetter = props.section.charAt(0).toUpperCase();
    const section = upperFirstLetter + props.section.substr(1, props.section.length - 1);
    const text = (props.section === 'code')
      ? "You're uploading some large files to the Code Section, are you sure you don't want to place these in the Input Section? Note, putting large files in the Code Section can hurt performance"
      : `You're uploading some large files to the ${section} Section, are you sure you don't want to place these in a Dataset?`;
    return text;
  }

  /**
  *  @param {object}
  *  gets file prompt text individual sections
  *  @return {string}
  */
  _getKeys(files, type) {
    const { state } = this;
    const objectKeys = files ? Object.keys(files) : [];
    const filteredKeys = objectKeys.filter((child) => {
      const isType = (type === 'folder') ? files[child].edge.node.isDir : !files[child].edge.node.isDir;
      return files[child].edge && isType;
    });

    const keys = this._childSort(filteredKeys, state.sort, state.reverse, files, type);

    return keys;
  }

  render() {
    const { props, state } = this;
    const { mutationData, files } = state;
    const { isOver } = props;
    const folderKeys = this._getKeys(files, 'folder');
    const fileKeys = this._getKeys(files, 'files');
    const childrenKeys = folderKeys.concat(fileKeys);
    const { isSelected } = this._checkChildState();
    const allFilesLocal = checkLocalAll(files);
    const uploadPromptText = this._getFilePromptText();
    // declare css
    const fileBrowserCSS = classNames({
      FileBrowser: true,
      'FileBrowser--linkVisible': state.showLinkModal,
      'FileBrowser--highlight': isOver,
      'FileBrowser--dropzone': fileKeys.length === 0,
    });
    const deleteButtonCSS = classNames({
      'Btn Btn--round Btn__delete Btn--noShadow Btn--action': true,
      hidden: !isSelected,
    });
    const multiSelectButtonCSS = classNames({
      'Btn--multiSelect': true,
      'Btn Btn--round Btn--medium': true,
      Btn__check: state.multiSelect === 'all',
      Btn__uncheck: state.multiSelect === 'none',
      Btn__partial: state.multiSelect === 'partial',
    });
    const nameHeaderCSS = classNames({
      'FileBrowser__name-text FileBrowser__header--name flex justify--start Btn--noStyle': true,
      'FileBroser__sort--asc': state.sort === 'az' && !state.reverse,
      'FileBroser__sort--desc': state.sort === 'az' && state.reverse,
    });
    const sizeHeaderCSS = classNames({
      'FileBrowser__header--size Btn--noStyle': true,
      'FileBroser__sort--asc': state.sort === 'size' && !state.reverse,
      'FileBroser__sort--desc': state.sort === 'size' && state.reverse,
    });
    const modifiedHeaderCSS = classNames({
      'FileBrowser__header--date Btn--noStyle': true,
      'FileBroser__sort--asc': state.sort === 'modified' && !state.reverse,
      'FileBroser__sort--desc': state.sort === 'modified' && state.reverse,
    });
    const popupCSS = classNames({
      FileBrowser__popup: true,
      hidden: !state.popupVisible,
      Tooltip__message: true,
    });
    const multiSelectCSS = classNames({
      'FileBrowser__multiselect flex justify--start': true,
      'box-shadow-50': isSelected,
    });
    const downloadAllCSS = classNames({
      'FileBrowser__button Tooltip-data Tooltip-data--small': true,
      'FileBrowser__button--download-all': !state.downloadingAll && !allFilesLocal,
      'FileBrowser__button--downloaded': !state.downloadingAll && allFilesLocal,
      'FileBrowser__button--downloading': state.downloadingAll,
    });

    return (
      props.connectDropTarget(<div
        ref={ref => ref}
        className={fileBrowserCSS}
        style={{ zIndex: state.fileSizePromptVisible ? 13 : 0 }}
      >
        { state.showLinkModal
            && (
            <LinkModal
              closeLinkModal={() => this.setState({ showLinkModal: false })}
              linkedDatasets={props.linkedDatasets || []}
            />
            )
         }
        { state.fileSizePromptVisible
             && (
             <Modal
               header="Large File Warning"
               handleClose={() => this._cancelUpload()}
               size="medium"
               renderContent={() => (
                 <div className="FileBrowser__modal-body flex justify--space-between flex--column">

                   <p>{ uploadPromptText }</p>

                   <div className="FileBrowser__button-container flex justify--space-around">

                     <button
                       type="button"
                       className="Btn--flat"
                       onClick={() => this._cancelUpload()}
                     >
                     Cancel Upload
                     </button>

                     <button
                       type="button"
                       onClick={() => this._userRejectsUpload()}
                     >
                        Skip Large Files
                     </button>

                     <button
                       type="button"
                       onClick={() => this._userAcceptsUpload()}
                     >
                       Continue Upload
                     </button>

                   </div>

                 </div>
               )

             }
             />
             )
         }
        <div className="FileBrowser__menu">
          <h5>Files</h5>
          <div className="FileBrowser__menu-buttons">
            <button
              className="FileBrowser__button Btn--round Btn--bordered Btn__upArrow"
              onClick={() => this.setState({ addFolderVisible: !state.addFolderVisible })}
              type="button"
            />
            <span>Upload Files</span>
            <button
              className="FileBrowser__button Btn--round Btn--bordered Btn__addFolder"
              onClick={() => this.setState({ addFolderVisible: !state.addFolderVisible })}
              type="button"
            />
            <span>New Folder</span>
            <button
              type="button"
              className="FileBrowser__button Btn--round Btn--bordered Btn__addDataset"
              onClick={() => this.setState({ showLinkModal: true })}
              data-tooltip="Link Dataset"
            />
            <span>Link Dataset</span>
          </div>
        </div>
        <div className="FileBrowser__tools flex justify--space-between">

          <div className="FileBrowser__search flex-1">
            <input
              className="FileBrowser__input search"
              type="text"
              placeholder="Search Files Here"
              onChange={(evt) => { this._updateSearchState(evt); }}
              onKeyUp={(evt) => { this._updateSearchState(evt); }}
            />
          </div>
        </div>
        <div className="FileBrowser__header">
          <div className={multiSelectCSS}>
            <button
              type="button"
              className={multiSelectButtonCSS}
              onClick={() => { this._selectFiles(); }}
            />
            <button
              type="button"
              className={deleteButtonCSS}
              onClick={() => { this._togglePopup(true); }}
            />

            <div className={popupCSS}>
              <div className="Tooltip__pointer" />
              <p>Are you sure?</p>
              <div className="flex justify--space-around">
                <button
                  type="button"
                  className="File__btn--round File__btn--cancel File__btn--delete"
                  onClick={() => { this._togglePopup(false); }}
                />
                <button
                  type="button"
                  className="File__btn--round File__btn--add File__btn--delete-files"
                  onClick={() => { this._deleteSelectedFiles(); }}
                />
              </div>
            </div>
          </div>
          <button
            className={nameHeaderCSS}
            onClick={() => this._handleSort('az')}
            type="button"
          >
            File
          </button>

          <button
            className={sizeHeaderCSS}
            onClick={() => this._handleSort('size')}
            type="button"
          >
            Size
          </button>

          <button
            className={modifiedHeaderCSS}
            onClick={() => this._handleSort('modified')}
            type="button"
          >
            Modified
          </button>

          <div className="FileBrowser__header--menu flex flex--row justify--right">
            { (props.section === 'data')
              && (
              <button
                className={downloadAllCSS}
                onClick={() => this._handleDownloadAll(allFilesLocal)}
                data-tooltip={allFilesLocal ? 'Downloaded' : 'Download All'}
                type="button"
              >
                { state.downloadingAll && <div /> }
              </button>
              )
            }
          </div>
        </div>
        <div className="FileBrowser__body">
          <AddSubfolder
            key="rootAddSubfolder"
            folderKey=""
            mutationData={mutationData}
            mutations={state.mutations}
            setAddFolderVisible={visibility => this.setState({ addFolderVisible: visibility })}
            addFolderVisible={state.addFolderVisible}
          />

          {

            childrenKeys.map((file) => {
              const isDir = files[file] && files[file].edge && files[file].edge.node.isDir;
              const isFile = files[file] && files[file].edge && !files[file].edge.node.isDir;
              const isDataset = files[file] && files[file].edge && files[file].edge.node.isDataset;
              if (isDataset) {
                const currentDataset = props.linkedDatasets.filter(
                  dataset => dataset.name === file,
                )[0];
                const commitsBehind = currentDataset && currentDataset.commitsBehind;
                return (
                  <Dataset
                    ref={file}
                    filename={file}
                    section={props.section}
                    key={files[file].edge.node.key}
                    multiSelect={state.multiSelect}
                    mutationData={mutationData}
                    fileData={files[file]}
                    mutations={state.mutations}
                    setState={this._setState}
                    sort={state.sort}
                    reverse={state.reverse}
                    childrenState={state.childrenState}
                    updateChildState={this._updateChildState}
                    codeDirUpload={this._codeDirUpload}
                    commitsBehind={commitsBehind}
                  />
                );
              } if (isDir) {
                return (
                  <Folder
                    ref={file}
                    filename={file}
                    key={files[file].edge.node.key}
                    multiSelect={state.multiSelect}
                    mutationData={mutationData}
                    fileData={files[file]}
                    isLocal={checkLocalIndividual(files[file])}
                    mutations={state.mutations}
                    setState={this._setState}
                    rowStyle={{}}
                    sort={state.sort}
                    reverse={state.reverse}
                    childrenState={state.childrenState}
                    section={props.section}
                    updateChildState={this._updateChildState}
                    parentDownloading={state.downloadingAll}
                    rootFolder
                    codeDirUpload={this._codeDirUpload}
                    checkLocal={checkLocalIndividual}
                  />
                );
              } if (isFile) {
                return (
                  <File
                    ref={file}
                    filename={file}
                    key={files[file].edge.node.key}
                    multiSelect={state.multiSelect}
                    mutationData={mutationData}
                    fileData={files[file]}
                    isLocal={checkLocalIndividual(files[file])}
                    childrenState={state.childrenState}
                    mutations={state.mutations}
                    expanded
                    section={props.section}
                    isOverChildFile={state.isOverChildFile}
                    updateParentDropZone={this._updateDropZone}
                    parentDownloading={state.downloadingAll}
                    updateChildState={this._updateChildState}
                    checkLocal={checkLocalIndividual}
                  />
                );
              }

              if (file && file.children[file]) {
                return (
                  <div style={file} />
                );
              }

              return (
                <div key={file}>
                  Loading
                </div>
              );
            })
          }
          { (childrenKeys.length === 0)
            && (
            <div className="FileBrowser__empty">
              { (state.search !== '')
                ? <h5>No files match your search.</h5>
                : <h5>Upload Files by Dragging & Dropping Here</h5>
               }
            </div>
            )
          }
          { props.isProcessing
            && (
            <div className="FileBrowser__veil">
              <span />
            </div>
            )
          }
        </div>
      </div>)
    );
  }
}

export default DropTarget(
  ['card', NativeTypes.FILE],
  Connectors.targetSource,
  Connectors.targetCollect,
)(FileBrowser);
