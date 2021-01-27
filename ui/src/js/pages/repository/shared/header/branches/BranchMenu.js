// vendor
import React, { Component } from 'react';
import classNames from 'classnames';
import { connect } from 'react-redux';
import uuidv4 from 'uuid/v4';
// store
import {
  setErrorMessage,
  setWarningMessage,
  setMultiInfoMessage,
} from 'JS/redux/actions/footer';
import { setSidepanelVisible } from 'JS/redux/actions/labbook/labbook';
// queries
import UserIdentity from 'JS/Auth/UserIdentity';
import LinkedLocalDatasetsQuery from 'Pages/repository/shared/header/actionsSection/queries/LinkedLocalDatasetsQuery';
// context
import ServerContext from 'Pages/ServerContext';
// componenets
import CreateBranch from 'Pages/repository/shared/modals/CreateBranch';
import ForceSync from 'Pages/repository/shared/modals/ForceSync';
import Branches from 'Pages/repository/shared/sidePanel/Branches';
import VisibilityModal from 'Pages/repository/shared/modals/visibility/VisibilityModal';
import PublishDatasetsModal from 'Pages/repository/shared/modals/publishDataset/PublishDatasetsModal';
import LoginPrompt from 'Pages/repository/shared/modals/LoginPrompt';
import SyncWarning from 'Components/modal/syncWarning/SyncWarning';
import PublishSyncErrorModal from './modal/PublishSyncErrorModal';
// utils
import BranchMutations from '../../utils/BranchMutations';
// assets
import './BranchMenu.scss';


/**
  @param {Array} branches
  filters array branhces and return the active branch node
  @return {Object} activeBranch
*/
const extraxtActiveBranch = (branches) => {
  const activeBranch = branches.filter(branch => branch.isActive)[0] || {};
  const filteredBranches = branches.filter(branch => !branch.isActive);
  const branchMenuList = (filteredBranches.length > 3)
    ? filteredBranches.slice(0, 3) : filteredBranches;
  const otherBranchCount = filteredBranches.length - branchMenuList.length;

  return ({
    activeBranch,
    filteredBranches,
    branchMenuList,
    otherBranchCount,
  });
};

/**
  @param {Object} props
  @param {Object} data
  Gets sync tooltip
  @return {String}
*/
const getSyncTooltip = (
  props,
  data,
  currentServer,
  isDataset,
  publishSyncError,
) => {
  const {
    hasWriteAccess,
    syncOrPublish,
    sectionCollabs,
    activeBranch,
  } = data;
  const {
    defaultRemote,
    isLockedSync,
  } = props;
  const repositoryType = isDataset ? 'Dataset' : 'Project';
  let syncTooltip = !hasWriteAccess ? 'Pull changes from Gignatum Hub' : `Sync changes to ${currentServer.name}`;
  syncTooltip = !defaultRemote
    ? `Click Publish to push branch to ${currentServer.name}`
    : syncTooltip;
  syncTooltip = isLockedSync
    ? `Cannot ${syncOrPublish} while ${repositoryType} is in use`
    : syncTooltip;
  syncTooltip = (activeBranch.branchName !== 'master' && !defaultRemote)
    ? 'Must publish Master branch first'
    : syncTooltip;
  syncTooltip = defaultRemote && !sectionCollabs
    ? `Please wait while ${repositoryType} data is being fetched`
    : syncTooltip;

  syncTooltip = publishSyncError
    ? `An error occured during ${syncOrPublish}ing, click to see more detail.`
    : syncTooltip;


  return syncTooltip;
};

/**
  @param {Object} props
  @param {Object} data
  Gets managed tooltip
  @return {String}
*/
const getManagedToolip = (props, data) => {
  const { state, defaultDatasetMessage } = data;
  let managedTooltip = props.isLocked ? 'Cannot Manage Branches while Project is in use' : 'Manage Branches';
  managedTooltip = state.isDataset ? defaultDatasetMessage : 'Manage Branches';

  return managedTooltip;
};


/**
  @param {Object} result
  @param {Object} data
  Gets managed tooltip
  @return {String}
*/
const getLocalDatasets = (result) => {
  const { data } = result;
  let localDataset = [];

  if (data && data.labbook) {
    const { linkedDatasets } = data.labbook;
    localDataset = linkedDatasets.filter((linkedDataset) => {
      const { defaultRemote } = linkedDataset;
      return (defaultRemote && (defaultRemote.slice(0, 4) !== 'http'));
    });
  }

  return localDataset;
};


/**
*  @param {Object} - activeBranch
*  determines whether or not user has write access
*  @return {}
*/
const checkForWriteAccess = (activeBranch, defaultRemote, collaborators, sectionName) => {
  const username = localStorage.getItem('username');

  if (!defaultRemote) {
    return true;
  }

  if (!collaborators
    || (collaborators && !collaborators[sectionName])) {
    return false;
  }
  const collaboratorsSection = collaborators[sectionName];
  const filteredArr = collaboratorsSection.filter(
    collaborator => (collaborator.collaboratorUsername === username),
  );

  if (filteredArr.length === 0) {
    return false;
  } if ((filteredArr[0].permission === 'READ_ONLY')
    || ((filteredArr[0].permission === 'READ_WRITE')
    && (activeBranch.branchName === 'master'))) {
    return false;
  }
  return true;
};

/**
* Method returns text for publish sync button
*  @param {string} defaultRemote
*  @param {boolean} publishSyncError
*  @param {boolean} showPullOnly

*  @return {string}
*/
const getPublishSyncText = (
  defaultRemote,
  publishSyncError,
  showPullOnly,
) => {
  const syncButtonText = defaultRemote
    ? showPullOnly
      ? 'Pull'
      : 'Sync'
    : 'Publish';
  if (defaultRemote) {
    if (publishSyncError) {
      return 'Sync Error';
    }
    if (showPullOnly) {
      return 'Pull';
    }

    return 'Sync';
  }

  if (publishSyncError) {
    return 'Publish Error';
  }
  return 'Publish';
};


type Props = {
  branches: string,
  collaborators: Object,
  defaultRemote: string,
  isExporting: boolean,
  isLocked: boolean,
  isLockedSync: boolean,
  isSticky: boolean,
  name: string,
  owner: string,
  sectionId: string,
  section: {
    name: string,
    owner: string,
    description: string,
  },
  sectionType: string,
  setBranchUptodate: Function,
  setSyncingState: Function,
  setPublishingState: Function,
  updateMigationState: Function,
};

class BranchMenu extends Component<Props> {
  state = {
    switchMenuVisible: false,
    createBranchVisible: false,
    branchMutations: new BranchMutations({
      parentId: this.props.sectionId,
      name: this.props.section.name,
      owner: this.props.section.owner,
    }),
    isPublishSyncErroModalVisible: false,
    forceSyncModalVisible: false,
    publishModalVisible: false,
    publishDatasetsModalVisible: false,
    publishDatasetsModalAction: 'Publish',
    publishSyncError: false,
    publishSyncErrorData: null,
    syncMenuVisible: false,
    showLoginPrompt: false,
    showSyncWarning: false,
    switchingBranch: false,
    isDataset: (this.props.sectionType !== 'labbook'),
    action: null,
    warningAction: 'publish',
  };


  static getDerivedStateFromProps(props, state) {
    const { publishFromCollaborators } = props;
    const { publishModalVisible } = state;

    return {
      ...state,
      publishModalVisible: publishFromCollaborators || publishModalVisible,
    };
  }

  componentDidMount() {
    window.addEventListener('click', this._closePopups);
  }

  componentWillUnmount() {
    window.removeEventListener('click', this._closePopups);
  }

  /**
  *  @param {}
  *  returns UserIdentityQeury promise
  *  @return {promise}
  */
  _checkSessionIsValid = () => (UserIdentity.getUserIdentity())

  /**
    @param {}
    calls reset branch on activebranch
  */
  _resetBranch = () => {
    const { setBranchUptodate, section } = this.props;
    const { owner, name } = section;
    this._toggleCover('Resetting Branch');
    this.state.branchMutations.resetBranch((response, error) => {
      if (error) {
        setErrorMessage(owner, name, 'Failed to reset branch.', error);
      }
      this._toggleCover(null);
      setBranchUptodate();
    });
    this.setState({ popupVisible: false });
  }

  /**
  *  @param {Array} branches
  *  filters array branhces and return the active branch node
  *  @return {Object} activeBranch
  */
  _setModalState = (key) => {
    const { state } = this;
    const { isLocked } = this.props;

    const value = !state[key];
    if (!isLocked && !state.isDataset) {
      this.setState({ [key]: value });
    }
  }

  /**
    @param {String} action
    handles labbook cover toggle
    @return {}
  */
  _toggleCover = (action) => {
    // TODO don't use getElementById to set classNames
    if (action) {
      this.setState({ action });
      if (document.getElementById('labbook__cover')) {
        document.getElementById('labbook__cover').classList.remove('hidden');
      }
    } else {
      this.setState({ action: false });
      if (document.getElementById('labbook__cover')) {
        document.getElementById('labbook__cover').classList.add('hidden');
      }
    }
  }

  /**
    @param {Array} branches
    filters array branhces and return the active branch node
    @return {Object} activeBranch
  */
  _switchBranch = (branch) => {
    const { branchMutations } = this.state;
    const { section, updateMigationState } = this.props;
    const { owner, name } = section;
    const self = this;
    const data = {
      branchName: branch.branchName,
    };

    this.setState({
      switchingBranch: branch.branchName,
      switchMenuVisible: false,
    });

    this._toggleCover('Switching Branches');

    branchMutations.switchBranch(data, (response, error) => {
      if (error) {
        setErrorMessage(owner, name, 'Failed to switch branches.', error);
      }
      self.setState({ switchingBranch: false });
      updateMigationState(response);

      branchMutations.buildImage((buildResponse, buildError) => {
        setTimeout(() => {
          this._toggleCover(null);
        }, 3000);
        if (buildError) {
          setErrorMessage(owner, name, 'Failed to switch branches.', buildError);
        }
      });
    });
  }

  /**
  *  @param {Boolean} queryForLocalDatasets
  *  @param {Boolean} closePublishDatasetsModal
  *  adds remote url to labbook
  *  @return {string}
  */
  _togglePublishModal = (queryForLocalDatasets, closePublishDatasetsModal) => {
    const { isExporting, section } = this.props;

    if (isExporting) {
      const { owner, name } = section;
      setWarningMessage(owner, name, 'Publishing is currently only available on the main workspace branch.');
      this.setState({ publishWarningVisible: true });
    } else if (queryForLocalDatasets && (typeof queryForLocalDatasets === 'boolean')) {
      LinkedLocalDatasetsQuery.getLocalDatasets({
        owner: section.owner,
        name: section.name,
      }).then((res) => {
        const localDatasets = res.data && res.data.labbook.linkedDatasets.filter(linkedDataset => linkedDataset.defaultRemote && linkedDataset.defaultRemote.slice(0, 4) !== 'http');
        if (localDatasets.length === 0) {
          this.setState((state) => {
            const publishModalVisible = !state.publishModalVisible;
            return { publishModalVisible };
          });
        } else {
          this.setState((state) => {
            const publishDatasetsModalVisible = !state.publishDatasetsModalVisible;
            return {
              localDatasets,
              publishDatasetsModalVisible,
              publishDatasetsModalAction: 'Publish',
            };
          });
        }
      });
    } else if (closePublishDatasetsModal) {
      this.setState((state) => {
        const publishDatasetsModalVisible = !state.publishDatasetsModalVisible;
        return { publishDatasetsModalVisible };
      });
    } else {
      this.setState((state) => {
        const publishModalVisible = !state.publishModalVisible;
        return { publishModalVisible };
      });
    }
  }

  /**
  *  @param {}
  *  resets state after publish
  *  @return {}
  */
  _resetState = () => {
    this.setState({
      remoteUrl: '',
      showLoginPrompt: true,
    });
  }

  /**
  *  @param {}
  *  resets state after publish
  *  @return {}
  */
  _resetPublishState = (publishDisabled) => {
    this.setState({
      menuOpen: false,
      publishDisabled,
    });
  }

  /**
    @param {} -
    sets state to toggle the switch dropdown
    @return {}
  */
  _toggleBranchSwitch = () => {
    const { isLocked } = this.props;
    const { isDataset } = this.state;

    if (!isLocked && !isDataset) {
      this.setState((state) => {
        const switchMenuVisible = !state.switchMenuVisible;
        return { switchMenuVisible };
      });
    }
  }

  /**
    @param {} -
    sets state to toggle the switch dropdown
    @return {}
  */
  _closePopups = (evt) => {
    if (evt.target.className.indexOf('BranchMenu') < 0) {
      this.setState({
        switchMenuVisible: false,
      });
    }
    if (evt.target.className.indexOf('Btn--branch--sync-dropdown') < 0) {
      this.setState({
        syncMenuVisible: false,
      });
    }
  }

  /**
    @param {} -
    sets state to toggle the switch dropdown
    @return {}
  */
  _toggleSidePanel = (sidePanelVisible) => {
    const { props } = this;
    const { isLocked, sectionType } = this.props;
    const { owner, name } = props[sectionType];
    const { isDataset } = this.state;

    if (!isLocked && !isDataset) {
      this.setState({ switchMenuVisible: false });
      setSidepanelVisible(owner, name, sidePanelVisible);
    }
  }

  /**
  *  @param {}
  *  closes login prompt modal
  *  @return {}
  */
  _closeLoginPromptModal = () => {
    this.setState({ showLoginPrompt: false });
  }

  /**
  *  @param {Boolean} - commitsHovered
  *  sets hoverstate for committs
  *  @return {}
  */
  _hovercommits = (commitsHovered) => {
    this.setState({ commitsHovered });
  }

  /**
  *  @param {Boolean} blockReset
  *  toggles reset popup
  *  @return {}
  */
  _toggleResetPopup = (blockReset) => {
    if (!blockReset) {
      this.setState((state) => {
        const popupVisible = !state.popupVisible;
        return { popupVisible };
      });
    }
  }

  /**
    sets state to toggle the switch dropdown
    @return {}
  */
  _toggleSyncDropdown = () => {
    this.setState((state) => {
      const syncMenuVisible = !state.syncMenuVisible;
      return { syncMenuVisible };
    });
  }

  /**
  *  @param {}
  *  resets state after publish
  *  @return {}
  */
  _setRemoteSession = () => {
    const { owner, labbookName } = this.state;
    const { currentServer } = this.context;
    const { baseUrl } = currentServer;
    this.setState({
      addedRemoteThisSession: true,
      remoteUrl: `${baseUrl}${owner}/${labbookName}`,
    });
  }

  /**
  * @param {Object} data
  * syncs dataset
  */
  _syncDataset = (data) => {
    const { branchMutations } = this.state;
    const { setSyncingState } = this.props;

    setSyncingState(true);
    branchMutations.syncDataset(data, (response, error) => {
      if (error) {
        data.failureCall(error);
      }
    });
  }

  /**
  * @param {Object} data
  * @param {function} passedSuccessCall
  * @param { Boolean} pullOnly
  * checks if project has a any published datasets and pops modal to sync them
  * or syncs project if none present
  */
  _syncLabbook = (data, passedSuccessCall, pullOnly) => {
    const { props, state } = this;
    const { syncLabbook } = state.branchMutations;
    const { owner, name } = props.section;

    props.setSyncingState(true);

    LinkedLocalDatasetsQuery.getLocalDatasets({
      owner,
      name,
    }).then((linkedQueryResponse) => {
      const localDatasets = getLocalDatasets(linkedQueryResponse);

      if ((localDatasets.length === 0) || pullOnly) {
        props.setSyncingState(true);

        syncLabbook(data, (response, error) => {
          if (error) {
            data.failureCall(error);
          }
          if (passedSuccessCall) {
            passedSuccessCall();
          }
        });
      } else {
        this.setState({
          localDatasets,
          publishDatasetsModalVisible: !state.publishDatasetsModalVisible,
          publishDatasetsModalAction: 'Sync',
        });

        props.setSyncingState(false);
      }
    });
  }

  /**
  *  @param {Boolean} - pullOnly
  *  @param {Boolean} - allowSync
  *  @param {Boolean} - allowSyncPull
  *  @param {Function} - passedSuccessCall
  *  @param {Boolean} - isLocked
  *  @param {Boolean} - overrideLock
  *  handles syncing or publishing the project
  *  @return {}
  */
  _handleSyncButton = (
    pullOnly,
    allowSync,
    allowSyncPull,
    passedSuccessCall,
    isLocked,
    overrideLock,
  ) => {
    // TODO refactor this function

    const {
      defaultRemote,
      section,
      sectionType,
      setBranchUptodate,
      setSyncingState,
    } = this.props;
    const { owner } = section;
    const { isDataset, publishSyncError } = this.state;
    const { buildImage } = this.state.branchMutations;

    if (publishSyncError) {
      this.setState({ isPublishSyncErroModalVisible: true });
      return;
    }

    if (isLocked && !overrideLock) {
      const warningAction = defaultRemote ? 'sync' : 'publish';
      this.setState({ showSyncWarning: true, warningAction });
      return;
    }
    this.setState({ syncMenuVisible: false, showSyncWarning: false });


    if (allowSync || (pullOnly && allowSyncPull)) {
      if (!defaultRemote) {
        this._togglePublishModal(!isDataset, false);
      } else {
        setSyncingState(true);
        const self = this;
        const data = {
          successCall: () => {
            if (sectionType === 'labbook') {
              if (!isLocked) {
                buildImage((response, error) => {
                  if (error) {
                    console.error(error);
                    const messageData = {
                      id: uuidv4(),
                      message: `ERROR: Failed to build ${section.name}`,
                      isLast: null,
                      error: true,
                      messageBody: error,
                    };
                    setMultiInfoMessage(owner, section.name, messageData);
                  }
                });
              }
              setBranchUptodate();
            }
            setSyncingState(false);
          },
          failureCall: (errorMessage, reportedFailureMessage) => {
            setSyncingState(false);
            if (errorMessage.indexOf('Merge conflict') > -1) {
              self._toggleSyncModal();
              this.setState({ pullOnly });
            } else {
              this._setPublishErrorState(errorMessage, reportedFailureMessage);
            }
          },
          pullOnly: pullOnly || false,
        };

        this._checkSessionIsValid().then((response) => {
          if (!navigator.onLine) {
            self.setState({ showLoginPrompt: true });
          } else if (!(response.data
              && response.data.userIdentity
              && response.data.userIdentity.isSessionValid)) {
            self.setState({ showLoginPrompt: true });
          } else if (sectionType !== 'labbook') {
            this._syncDataset(data);
          } else {
            this._syncLabbook(data, passedSuccessCall, pullOnly);
          }
        });
      }
    }
  }

  /**
    *  @param {Object} activeBranch
    *  @param {Boolean} hasWriteAccess
    *  @param {Boolean} upToDate
    *  @param {Boolean} publishSyncError
    *  returns tooltip info
    *  @return {string}
    */
  _getTooltipText = (activeBranch, hasWriteAccess, upToDate, publishSyncError) => {
    // destructure here
    const { props, state } = this;
    const {
      collaborators,
      defaultRemote,
      isLocked,
      section,
    } = this.props;
    const { currentServer } = this.context;
    // other variables
    const sectionCollabs = (collaborators && collaborators[section.name]) || null;
    const defaultDatasetMessage = 'Datasets currently does not support branching features';
    const isPullOnly = defaultRemote && !hasWriteAccess && sectionCollabs;

    let syncOrPublish = defaultRemote ? 'Sync' : 'Publish';
    syncOrPublish = isPullOnly ? 'Pull' : syncOrPublish;

    let createTooltip = state.isDataset ? defaultDatasetMessage : 'Create Branch';
    createTooltip = isLocked ? 'Cannot Create Branch while Project is in use' : createTooltip;

    let resetTooltip = 'Reset Branch to Remote';
    resetTooltip = upToDate ? 'Branch up to date' : resetTooltip;
    resetTooltip = activeBranch.commitsAhead === undefined ? 'Please wait while branch data is being fetched' : resetTooltip;
    resetTooltip = !activeBranch.isRemote ? 'Cannot reset a branch until it has been published' : resetTooltip;
    resetTooltip = (!activeBranch.isRemote && (activeBranch.branchName !== 'master')) ? 'The master branch must be published first' : resetTooltip;
    resetTooltip = state.isLocked ? 'Cannot Reset Branch while Project is in use' : resetTooltip;
    resetTooltip = state.isDataset ? defaultDatasetMessage : resetTooltip;
    let switchTooltip = props.isLocked ? 'Cannot switch branches while Project is in use' : 'Switch Branches';
    switchTooltip = state.isDataset ? defaultDatasetMessage : switchTooltip;
    const commitsBehindText = activeBranch.commitsBehind ? `${activeBranch.commitsBehind} Commits Behind, ` : '';
    const commitsAheadText = activeBranch.commitsAhead ? `${activeBranch.commitsAhead} Commits Ahead` : '';
    const commitTooltip = `${commitsBehindText} ${commitsAheadText}`;

    const data = {
      defaultDatasetMessage,
      hasWriteAccess,
      syncOrPublish,
      sectionCollabs,
      activeBranch,
      state,
    };
    // TODO FIX this, nesting ternary operations is bad
    return {
      syncTooltip: getSyncTooltip(
        props,
        data,
        currentServer,
        state.isDataset,
        publishSyncError,
      ),
      manageTooltip: getManagedToolip(props, data),
      createTooltip,
      resetTooltip,
      switchTooltip,
      commitTooltip,
      syncOrPublish,
    };
  }

  /**
  *  @param {}
  *  toggles sync modal
  *  @return {string}
  */
 _toggleSyncModal = () => {
   this.setState((state) => {
     const forceSyncModalVisible = !state.forceSyncModalVisible;
     return {
       forceSyncModalVisible,
       publishDatasetsModalVisible: false,
     };
   });
 }

  /**
  * sets state for sync warning modal
  */
  _toggleSyncWarningModal = () => {
    this.setState({ showSyncWarning: false });
  }

  /**
  * Method sets error state on button error state for the SyncErrorModal
  * @param {string} errorMessage
  * @param {string} reportedFailureMessage
  *
  */
  _setPublishErrorState = (errorMessage, reportedFailureMessage) => {
    this.setState({
      publishSyncError: true,
      publishSyncErrorData: {
        header: errorMessage,
        message: reportedFailureMessage,
      },
    });
  }

  /**
  * Method clears error state
  *
  */
  _clearSyncErorrState = () => {
    this.setState({
      isPublishSyncErroModalVisible: false,
      publishSyncError: false,
      publishSyncErrorData: null,
    });
  }

 static contextType = ServerContext;

 render() {
   const { props, state } = this;
   const {
     collaborators,
     branches,
     defaultRemote,
     owner,
     name,
     isLocked,
     isLockedSync,
     isSticky,
     section,
     setSyncingState,
   } = this.props;
   const {
     forceSyncModalVisible,
     publishModalVisible,
     publishSyncErrorData,
     publishDatasetsModalVisible,
     isPublishSyncErroModalVisible,
     publishSyncError,
     showLoginPrompt,
     showSyncWarning,
     warningAction,
   } = this.state;
   const {
     activeBranch,
     filteredBranches,
     branchMenuList,
     otherBranchCount,
   } = extraxtActiveBranch(branches);
   // declare vars here
   const sectionCollabs = (collaborators && collaborators[section.name])
      || null;
   const waitingOnCollabs = !sectionCollabs;
   const hasWriteAccess = checkForWriteAccess(
     activeBranch,
     defaultRemote,
     collaborators,
     section.name,
   );
   const upToDate = (activeBranch.commitsAhead === 0)
    && (activeBranch.commitsBehind === 0);
   const allowSync = !((activeBranch.branchName !== 'master') && !defaultRemote)
    && hasWriteAccess && !isLockedSync;
   const allowSyncPull = !((activeBranch.branchName !== 'master') && !defaultRemote) && !isLockedSync
    && defaultRemote;
   const allowReset = !isLocked
    && !upToDate
    && activeBranch.isRemote
    && (activeBranch.commitsAhead !== undefined);
   const statusText = activeBranch.isRemote
     ? 'Local & Remote'
     : 'Local only';
   const showPullOnly = defaultRemote && !hasWriteAccess && !waitingOnCollabs;
   const disableDropdown = !allowSyncPull || !defaultRemote || showPullOnly || publishSyncError;
   const {
     syncTooltip,
     manageTooltip,
     createTooltip,
     resetTooltip,
     switchTooltip,
     commitTooltip,
     syncOrPublish,
   } = this._getTooltipText(activeBranch, hasWriteAccess, upToDate, publishSyncError);
   const syncButtonText = getPublishSyncText(defaultRemote, publishSyncError, showPullOnly);
   const syncButtonDisabled = (showPullOnly && !allowSyncPull)
    || (!defaultRemote && !allowSync)
    || (defaultRemote && !allowSync && !showPullOnly);

   // declare css here
   const switchDropdownCSS = classNames({
     'BranchMenu__dropdown-menu': true,
     hidden: !state.switchMenuVisible,
   });
   const branchMenuCSS = classNames({
     BranchMenu: true,
     hidden: isSticky,
   });
   const drodownButtonCSS = classNames({
     'BranchMenu__dropdown-btn': true,
     'BranchMenu__dropdown-btn--disabled': isLocked || state.isDataset,
     'BranchMenu__dropdown-btn--open': state.switchMenuVisible,
     'Tooltip-data Tooltip-data': isLocked || state.isDataset,
   });
   const branchNameCSS = classNames({
     'BranchMenu__branch-name': !state.switchingBranch,
     hidden: state.switchingBranch,
   });
   const branchSwitchingNameCSS = classNames({
     'BranchMenu__branch-name BranchMenu__branch-name--switching': state.switchingBranch,
     hidden: !state.switchingBranch,
   });
   const syncMenuDropdownCSS = classNames({
     'BranchMenu__dropdown-menu': state.syncMenuVisible && !disableDropdown,
     hidden: !state.syncMenuVisible,
   });
   const syncMenuDropdownButtonCSS = classNames({
     'Btn--branch Btn--action Btn--branch--sync-dropdown': true,
     'Btn--branch--sync-open': state.syncMenuVisible,
   });
   const syncCSS = classNames({
     'Btn--branch Btn--action Btn--branch--sync': true,
     'Btn--branch--sync--publish': !defaultRemote && !publishSyncError,
     'Btn--branch--sync--pull': showPullOnly && !publishSyncError,
     'Btn--branch--sync--upToDate': defaultRemote && (upToDate || (activeBranch.commitsAhead === undefined) || isLocked) && !showPullOnly && !publishSyncError,
     'Tooltip-data': !state.commitsHovered,
     'Btn--branch--error': publishSyncError,
   });
   const manageCSS = classNames({
     'Btn--branch Btn--action Btn--branch--manage': true,
     'Tooltip-data': true,
   });
   const resetCSS = classNames({
     'Btn--branch Btn--action Btn--branch--reset': true,
     'Tooltip-data': true,
   });
   const createCSS = classNames({
     'Btn--branch Btn--action Btn--branch--create': true,
     'Tooltip-data': true,
   });
   const popupCSS = classNames({
     BranchMenu__popup: true,
     hidden: !state.popupVisible,
   });

   return (
     <div className={branchMenuCSS}>
       <div className="BranchMenu__dropdown">
         {
            showSyncWarning
            && (
              <SyncWarning
                toggleSyncWarningModal={this._toggleSyncWarningModal}
                handleSync={() => this._handleSyncButton(showPullOnly, allowSync, allowSyncPull, null, isLocked, true)}
                warningAction={warningAction}
              />
            )
          }
         <div
           onClick={() => this._toggleBranchSwitch()}
           data-tooltip={switchTooltip}
           className={drodownButtonCSS}
           role="presentation"
         >
           <div className={branchNameCSS}>
             <div className="BranchMenu__dropdown-label">Branch:</div>
             <div className="BranchMenu__dropdown-text">{activeBranch.branchName}</div>
           </div>

           <div className={branchSwitchingNameCSS}>
             <span className="BranchMenu__dropdown-label">Branch:</span>
             <span className="BranchMenu__dropdown-text ">
               {`switching to ${state.switchingBranch}...`}
             </span>
           </div>
           <div
             className="BranchMenu__status Tooltip-data Tooltip-data--small"
             data-tooltip={statusText}
           >
             { activeBranch.isLocal
               ? <div className="BranchMenu__status--local" />
               : <div />}
             { activeBranch.isRemote
               ? <div className="BranchMenu__status--remote" />
               : <div />}
           </div>
         </div>
         <div className={switchDropdownCSS}>
           <h5 className="BranchMenu__h5">Quick Switch</h5>
           <ul className="BranchMenu__ul">
             { branchMenuList.map((branch) => {
               const cloudIconCSS = classNames({
                 BranchMenu__icon: true,
                 'BranchMenu__icon--cloud': branch.isRemote,
                 'BranchMenu__icon--empty': !branch.isRemote,
               });
               const localIconCSS = classNames({
                 BranchMenu__icon: true,
                 'BranchMenu__icon--local': branch.isLocal,
                 'BranchMenu__icon--empty': !branch.isLocal,
               });

               return (
                 <li
                   onClick={() => this._switchBranch(branch)}
                   key={branch.branchName}
                   className="BranchMenu__list-item"
                   role="presentation"
                 >
                   <div className="BranchMenu__text">{branch.branchName}</div>
                   <div className="BranchMenu__icons">
                     <div className={cloudIconCSS} />
                     <div className={localIconCSS} />
                   </div>
                 </li>
               );
             })}

             { (otherBranchCount > 0)
               && <div className="BranchMenu__other-text">{`+${otherBranchCount} others` }</div>}

             { (filteredBranches.length === 0)
                && (
                  <li
                    className="BranchMenu__list-item BranchMenu__list-item--create"
                    onClick={() => this._setModalState('createBranchVisible')}
                    role="presentation"
                  >
                    No other branches.
                    <button
                      type="button"
                      className="Btn--flat"
                    >
                      Create a new branch?
                    </button>
                  </li>
                )}
           </ul>
           <div className="BranchMenu__menu-button">
             <button
               type="button"
               onClick={() => this._toggleSidePanel(true)}
               className="BranchMenu__button Btn--flat"
             >
               Manage Branches
             </button>
           </div>
         </div>
       </div>
       { !state.action
         ? (
           <div className="BranchMenu__buttons">
             <button
               onClick={() => this._toggleSidePanel(true)}
               className={manageCSS}
               disabled={isLocked || state.isDataset}
               data-tooltip={manageTooltip}
               type="button"
             />
             <button
               className={createCSS}
               type="button"
               disabled={isLocked || state.isDataset}
               data-tooltip={createTooltip}
               onClick={() => this._setModalState('createBranchVisible')}
             />
             <div className="BranchMenu__reset-container">
               <button
                 className={resetCSS}
                 type="button"
                 disabled={!allowReset || state.isDataset}
                 data-tooltip={resetTooltip}
                 onClick={() => this._toggleResetPopup(!allowReset || state.isDataset)}
               />
               <div className={popupCSS}>
                 <p>You are about to reset this branch. Resetting a branch will get rid of local changes. Click 'Confirm' to proceed.</p>
                 <div className="flex justify--space-around">
                   <button
                     type="button"
                     className="Btn--flat"
                     onClick={() => { this._toggleResetPopup(); }}
                   >
                     Cancel
                   </button>
                   <button
                     type="button"
                     className="BranchMenu__reset-confirm"
                     onClick={() => this._resetBranch()}
                   >
                     Confirm
                   </button>
                 </div>
               </div>
             </div>
             <div className="BranchMenu__sync-container">
               <button
                 className={syncCSS}
                 disabled={syncButtonDisabled}
                 onClick={() => { this._handleSyncButton(showPullOnly, allowSync, allowSyncPull, null, isLocked); }}
                 data-tooltip={syncTooltip}
                 type="button"
               >
                 { (!upToDate && allowSync && !publishSyncError
                   && (activeBranch.commitsAhead !== undefined)
                   && (activeBranch.commitsAhead !== null))
                  && (
                    <div
                      className="BranchMenu__sync-status Tooltip-data Tooltip-data--small"
                      data-tooltip={commitTooltip}
                      onMouseEnter={() => this._hovercommits(true)}
                      onMouseLeave={() => this._hovercommits(false)}
                    >
                      { ((activeBranch.commitsBehind !== 0)
                        && (activeBranch.commitsBehind !== null))
                        && (
                          <div className="BranchMenu__sync-status--commits-behind">
                            { activeBranch.commitsBehind }
                          </div>
                        )}
                      { ((activeBranch.commitsAhead !== 0)
                        && (activeBranch.commitsAhead !== null))
                        && (
                          <div className="BranchMenu__sync-status--commits-ahead">
                            { activeBranch.commitsAhead }
                          </div>
                        )}
                    </div>
                  )}

                 { publishSyncError
                    && <div className="BranchMenu__icon BranchMenu__icon--error" />}
                 <div className="Btn--branch--text">{syncButtonText}</div>
               </button>

               <button
                 className={syncMenuDropdownButtonCSS}
                 disabled={disableDropdown}
                 onClick={() => { this._toggleSyncDropdown(); }}
                 type="submit"
               />

               <div className={syncMenuDropdownCSS}>
                 <h5 className="BranchMenu__h5">Remote Action</h5>
                 <ul className="BranchMenu__ul">
                   { allowSync
                      && (
                      <li
                        className="BranchMenu__list-item"
                        onClick={() => this._handleSyncButton(false, allowSync, allowSyncPull, null, isLocked)}
                        role="presentation"
                      >
                        Sync (Pull then Push)
                      </li>
                      )}
                   <li
                     className="BranchMenu__list-item"
                     onClick={() => this._handleSyncButton(true, allowSync, allowSyncPull, null, isLocked)}
                     role="presentation"
                   >
                     Pull (Pull-only)
                   </li>
                 </ul>
               </div>
             </div>
           </div>
         )
         : <div className="BranchMenu__action">{state.action}</div>}

       <CreateBranch
         owner={owner}
         name={name}
         modalVisible={state.createBranchVisible}
         description={section.description}
         toggleModal={this._setModalState}
       />

       <Branches
         {...this.props}
         toggleSidePanel={this._toggleSidePanel}
         disableDropdown={disableDropdown}
         activeBranch={activeBranch}
         toggleModal={this._setModalState}
         isSticky={isSticky}
         branchMutations={state.branchMutations}
         isLocked={isLocked}
         handleSyncButton={this._handleSyncButton}
         waitingOnCollabs={waitingOnCollabs}
         allowSync={allowSync}
         allowSyncPull={allowSyncPull}
         sectionId={props.sectionId}
         syncTooltip={syncTooltip}
         switchBranch={this._switchBranch}
         toggleCover={this._toggleCover}
         showPullOnly={showPullOnly}
         labbookName={section.name}
         owner={owner}
         name={name}
       />

       <VisibilityModal
         {...this.props}
         isVisible={publishModalVisible}
         owner={section.owner}
         name={section.name}
         labbookId={props.sectionId}
         remoteUrl={defaultRemote}
         buttonText="Publish"
         header="Publish"
         modalStateValue="visibilityModalVisible"
         checkSessionIsValid={this._checkSessionIsValid}
         toggleModal={this._togglePublishModal}
         resetState={this._resetState}
         resetPublishState={this._resetPublishState}
         setPublishErrorState={this._setPublishErrorState}
         setRemoteSession={this._setRemoteSession}
         setSyncingState={setSyncingState}
       />

       <PublishDatasetsModal
         {...this.props}
         isVisible={publishDatasetsModalVisible}
         owner={props.section.owner}
         name={props.section.name}
         labbookId={props.sectionId}
         buttonText="Publish All"
         header={state.publishDatasetsModalAction}
         pullOnly={state.pullOnly}
         modalStateValue="visibilityModalVisible"
         toggleSyncModal={this._toggleSyncModal}
         checkSessionIsValid={this._checkSessionIsValid}
         toggleModal={this._togglePublishModal}
         resetState={this._resetState}
         resetPublishState={this._resetPublishState}
         setRemoteSession={this._setRemoteSession}
         handleSync={this._handleSyncButton}
         localDatasets={state.localDatasets || []}
         setPublishErrorState={this._setPublishErrorState}
       />

       <ForceSync
         {...this.props}
         isVisible={forceSyncModalVisible}
         name={name}
         owner={owner}
         pullOnly={state.pullOnly}
         toggleSyncModal={this._toggleSyncModal}
         setPublishErrorState={this._setPublishErrorState}
       />

       <LoginPrompt
         showLoginPrompt={showLoginPrompt}
         closeModal={this._closeLoginPromptModal}
       />

       <PublishSyncErrorModal
         closeModal={this._clearSyncErorrState}
         data={publishSyncErrorData}
         isVisible={isPublishSyncErroModalVisible}
         remoteOperationPerformed={syncOrPublish}
       />
     </div>

   );
 }
}

const mapStateToProps = state => ({
  collaborators: state.collaborators.collaborators,
  publishFromCollaborators: state.collaborators.publishFromCollaborators,
});

const mapDispatchToProps = () => ({});

export default connect(mapStateToProps, mapDispatchToProps)(BranchMenu);
