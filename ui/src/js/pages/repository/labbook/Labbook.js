// vendor
import React, { Component } from 'react';
import { Route, Switch } from 'react-router-dom';
import {
  createRefetchContainer,
  graphql,
} from 'react-relay';
import { DragDropContext } from 'react-dnd';
import classNames from 'classnames';
import { connect } from 'react-redux';
// store
import store from 'JS/redux/store';
import { setContainerMenuWarningMessage } from 'JS/redux/actions/labbook/environment/environment';
import {
  setMergeMode,
  setBuildingState,
  setStickyState,
  updateTransitionState,
} from 'JS/redux/actions/labbook/labbook';
import { setCallbackRoute } from 'JS/redux/actions/routes';
// utils
import BranchMutations from 'Pages/repository/shared/utils/BranchMutations';
// mutations
import LabbookContainerStatusMutation from 'Mutations/repository/labbook/LabbookContainerStatusMutation';
import LabbookLookupMutation from 'Mutations/repository/labbook/LabbookLookupMutation';
// components
import Loader from 'Components/loader/Loader';
import Login from 'Pages/login/Login';
import ErrorBoundary from 'Components/errorBoundary/ErrorBoundary';
import Header from 'Pages/repository/shared/header/Header';
import Activity from './activity/LabbookActivityContainer';
import Overview from './overview/LabbookOverviewContainer';
import Environment from './environment/Environment';
import Code from './code/Code';
import InputData from './inputData/Input';
import OutputData from './outputData/Output';
import MigrationModal from './modals/migration/MigrationModal';
// query
import fetchMigrationInfoQuery from './queries/fetchMigrationInfoQuery';
// backend
import backend from './labbookBackend';
// assets
import './Labbook.scss';

let count = 0;
const containerStatusList = [];
/**
  scrolls to top of window
*/
const scrollToTop = () => {
  window.scrollTo(0, 0);
};

/**
   @param {Object} props
   determines if project is locked
   @return {Boolean}
  */
const determineIsLocked = (props) => {
  const {
    labbook,
    isBuilding,
    isSyncing,
    isPublishing,
    isUploading,
    globalIsUploading,
  } = props;

  return (
    (labbook.environment.containerStatus !== 'NOT_RUNNING')
    || (labbook.environment.imageStatus === 'BUILD_IN_PROGRESS')
    || (labbook.environment.imageStatus === 'BUILD_QUEUED')
    || isBuilding
    || isSyncing
    || isPublishing
    || isUploading
    || globalIsUploading
  );
};


type Props = {
  activityRecords: Array,
  auth: {
    isAuthenticated: Function,
  },
  branchesOpen: Boolean,
  detailMode: string,
  diskLow: Boolean,
  isBuilding: Boolean,
  isPublishing: Boolean,
  isSticky: Boolean,
  isSyncing: Boolean,
  labbook: {
    activeBranchName: string,
    branches: Array<Object>,
    defaultRemote: string,
    description: string,
    canManageCollaborators: Boolean,
    collaborators: Array<Object>,
    environment: {
      containerStatus: string,
      imageStatus: string,
      base: {
        developmentTools: Array
      },
    },
    id: string,
    name: string,
    owner: string,
  },
  labbookName: string,
  location: {
    pathname: string,
  },
  match: Object,
  relay: {
    refetch: Function,
  },
  sectionType: string,
  sidePanelVisible: Boolean,
}

class Labbook extends Component<Props> {
  state = {
    isLocked: determineIsLocked(this.props),
    collaborators: this.props.labbook.collaborators,
    canManageCollaborators: this.props.labbook.canManageCollaborators,
    branches: this.props.labbook.branches,
    deletedBranches: [],
    migrationInProgress: false,
    migrateComplete: false,
    branchMutations: new BranchMutations({
      parentId: this.props.labbook.id,
      name: this.props.labbook.name,
      owner: this.props.labbook.owner,
    }),
    isDeprecated: null,
    shouldMigrate: null,
    packageLatestVersions: [],
    isFetchingPackages: false,
    queuePackageFetch: false,
    activeBranchName: this.props.labbook.activeBranchName,
    overviewSkip: true,
    activitySkip: true,
    environmentSkip: true,
    codeSkip: true,
    inputSkip: true,
    outputSkip: true,
    lockFileBrowser: false,
    packageRefetchRan: false,
  }

  static getDerivedStateFromProps(nextProps, state) {
    setCallbackRoute(nextProps.location.pathname);
    const propBranches = nextProps.labbook && nextProps.labbook.branches
      ? nextProps.labbook.branches
      : [];
    const stateBranches = state.branches || [];
    const branchMap = new Map();
    const mergedBranches = [];
    const newDeletedBranches = state.deletedBranches.slice();
    const { isPublishing, isUploading, transitionState } = nextProps;

    propBranches.forEach((branch) => {
      if (newDeletedBranches.indexOf(branch.id) === -1) {
        branchMap.set(branch.id, branch);
      }
    });
    stateBranches.forEach((branch) => {
      if (branchMap.has(branch.id)) {
        const itemReference = branchMap.get(branch.id);
        const newItem = Object.assign({}, branch, itemReference);
        branchMap.set(branch.id, newItem);
      } else {
        newDeletedBranches.push(branch.id);
      }
    });

    branchMap.forEach((branch) => {
      mergedBranches.push(branch);
    });
    const isLocked = (nextProps.labbook
      && nextProps.labbook.environment.containerStatus !== 'NOT_RUNNING')
      || (nextProps.labbook.environment.imageStatus === 'BUILD_IN_PROGRESS')
      || (nextProps.labbook.environment.imageStatus === 'BUILD_QUEUED')
      || nextProps.isBuilding
      || nextProps.isSyncing
      || isPublishing
      || isUploading
      || nextProps.globalIsUploading
      || (transitionState === 'Starting')
      || (transitionState === 'Exporting');

    const canManageCollaborators = nextProps.labbook
      ? nextProps.labbook.canManageCollaborators
      : false;
    const collaborators = nextProps.labbook
      ? nextProps.labbook.collaborators
      : [];

    const lockFileBrowser = nextProps.isSyncing
      || nextProps.globalIsUploading
      || isPublishing
      || nextProps.isExporting;
    return {
      ...state,
      deletedBranches: newDeletedBranches,
      branches: mergedBranches,
      canManageCollaborators,
      collaborators,
      isLocked,
      lockFileBrowser,
    };
  }

  /**
    @param {}
    subscribe to store to update state
    set unsubcribe for store
  */
  componentDidMount() {
    const { props, state } = this;
    const { name, owner } = props.labbook;

    localStorage.setItem('owner', owner);
    setCallbackRoute(props.location.pathname);

    this.mounted = true;
    document.title = `${owner}/${name}`;

    props.auth.isAuthenticated().then((response) => {
      let isAuthenticated = response;
      if (isAuthenticated === null) {
        isAuthenticated = false;
      }
      if ((isAuthenticated !== state.authenticated) && this.mounted) {
        this.setState({ authenticated: isAuthenticated });
      }
    });

    this._fetchMigrationInfo();

    this._setStickHeader();
    this._fetchStatus(true);

    window.addEventListener('scroll', this._setStickHeader);
    window.addEventListener('click', this._branchViewClickedOff);
  }

  componentDidUpdate() {
    const { props, state } = this;
    const { activeBranchName } = props.labbook;
    // TODO do not set state in componenetDidUpdate
    if (activeBranchName !== state.activeBranchName) {
      this.setState({ activeBranchName });
    }
  }

  /**
    @param {}
    removes event listeners
  */
  componentWillUnmount() {
    this.mounted = false;

    window.removeEventListener('scroll', this._setStickHeader);
    window.removeEventListener('click', this._branchViewClickedOff);
  }

  /**
  @param {}
  cancels refetch packages
  */
  _cancelRefetch = () => {
    if (this.refetch && this.refetch.dispose) {
      this.refetch.dispose();
    }
  }

  /**
   @param {}
   refetch packages
   */
  _packageLatestRefetch = () => {
    const { props, state } = this;
    const queryVariables = {
      labbookID: props.labbook.id,
      skipPackages: false,
      environmentSkip: false,
      first: 1000,
    };
    const renderVariables = {
      labbookID: props.labbook.id,
      overviewSkip: false,
      activitySkip: false,
      environmentSkip: false,
      inputSkip: false,
      outputSkip: false,
      codeSkip: false,
      labbookSkip: false,
      skipPackages: false,
    };
    const options = {
      force: true,
    };
    if (!state.packageRefetchRan) {
      this.refetch = props.relay.refetch(queryVariables, renderVariables, () => {
        this.setState({ packageRefetchRan: true });
      }, options);
    }
  }

  /**
   @param {String} section
   refetch labbook
   */
  _refetchSection = (section) => {
    const { props, state } = this;
    const currentSection = `${section}Skip`;
    const currentState = {
      overviewSkip: state.overviewSkip,
      activitySkip: state.activitySkip,
      environmentSkip: state.environmentSkip,
      inputSkip: state.inputSkip,
      outputSkip: state.outputSkip,
      codeSkip: state.codeSkip,
    };
    const sections = ['overview', 'activity', 'environment', 'input', 'output', 'code'];
    const queryVariables = {
      labbookID: props.labbook.id,
      [currentSection]: false,
    };
    const renderVariables = {
      labbookID: props.labbook.id,
      ...currentState,
      [currentSection]: false,
      skipPackages: false,
    };
    const remainingQueryVariables = {
      labbookID: props.labbook.id,
      labbookSkip: false,
    };
    const remainingRenderVariables = {
      labbookID: props.labbook.id,
      labbookSkip: false,
      skipPackages: false,
    };
    const newState = {
      labbookSkip: true,
    };
    const options = {
      force: true,
    };

    sections.forEach((fragmentSection) => {
      const remainingSection = `${fragmentSection}Skip`;
      if (fragmentSection !== section) {
        remainingQueryVariables[remainingSection] = false;
        newState[remainingSection] = false;
      }
      remainingRenderVariables[remainingSection] = false;
    });

    const refetchCallback = () => {
      this.setState({ [currentSection]: false });
      props.relay.refetch(
        remainingQueryVariables,
        remainingRenderVariables,
        () => {
          this.setState(newState);
        },
        options,
      );
    };


    if (state[currentSection]) {
      props.relay.refetch(queryVariables, renderVariables, refetchCallback, options);
    }
  }

  /**
   * @param {}
   * checks if project is deprecated and should migrate and sets state
  */
  _fetchMigrationInfo = () => {
    const { props } = this;
    const { owner, name } = props.labbook;
    const self = this;

    fetchMigrationInfoQuery.getLabook(owner, name).then((response) => {
      if (response.labbook) {
        const {
          isDeprecated,
          shouldMigrate,
        } = response.labbook;
        self.setState({
          isDeprecated,
          shouldMigrate,
        });
      }
    });
  }

  /**
  *  @param {object} - response
  *  update state from switch mutation
  *  @return {}
  */
  _updateMigationState = (response) => {
    if (response && response.workonExperimentalBranch) {
      const { isDeprecated, shouldMigrate } = response.workonExperimentalBranch.labbook;
      this.setState({
        isDeprecated,
        shouldMigrate,
      });
    }
  }

  /**
  *  @param {} -
  *  fetches status of labbook container and image
  *  sets state of labbook using redux and containerStatus using setState
  *  @return {}
  */
  _fetchStatus = (isLabbookUpdate) => {
    const { props } = this;
    const { owner, name } = props.labbook;
    const self = this;
    const { isBuilding } = props;


    if (this.mounted) {
      if (!isLabbookUpdate) {
        LabbookContainerStatusMutation(owner, name, (error, response) => {
          if (response && response.fetchLabbookEdge && response.fetchLabbookEdge.newLabbookEdge) {
            const { environment } = response.fetchLabbookEdge.newLabbookEdge.node;
            containerStatusList.push(environment.imageStatus);
            const containerStatusLength = containerStatusList.length;
            const previousImageStatus = containerStatusList[containerStatusLength - 2];
            if (((previousImageStatus !== 'BUILD_IN_PROGRESS') || (previousImageStatus !== 'BUILD_FAILED'))
              && ((environment.imageStatus === 'EXISTS') || (environment.imageStatus === 'BUILD_FAILED'))
              && isBuilding) {
              setBuildingState(owner, name, false);
            }
            if ((previousImageStatus !== 'NOT_RUNNING')
              && (environment.containerStatus === 'RUNNING')) {
              updateTransitionState(owner, name, '');
            }
          }
          setTimeout(() => {
            const canLabbookUpdate = (count === 20);
            self._fetchStatus(canLabbookUpdate);
            count = canLabbookUpdate ? 0 : (count + 1);
          }, 3 * 1000);
        });
      } else {
        LabbookLookupMutation(owner, name, (error, response) => {
          if (response && response.fetchLabbookEdge && response.fetchLabbookEdge.newLabbookEdge) {
            const {
              branches,
              collaborators,
              canManageCollaborators,
            } = response.fetchLabbookEdge.newLabbookEdge.node;
            self.setState({
              branches,
              collaborators,
              canManageCollaborators,
            });
          }
          setTimeout(() => {
            const canLabbookUpdate = (count === 20);
            self._fetchStatus(canLabbookUpdate);
            count = canLabbookUpdate ? 0 : (count + 1);
          }, 3 * 1000);
        });
      }
    }
  }

  /**
    @param {event}
    updates state of labbook when prompted ot by the store
    updates history prop
  */
  _branchViewClickedOff = (evt) => {
    if (evt.target.className.indexOf('Labbook__veil') > -1) {
      this._toggleBranchesView(false, false);
    }
  }

  /**
    sets branch uptodate in state
  */
  _setBranchUptodate = () => {
    const { branches } = this.state;
    const activePosition = branches.map(branch => branch.isActive).indexOf(true);
    const branchesClone = branches.slice();
    branchesClone[activePosition].commitsBehind = 0;
    branchesClone[activePosition].commitsAhead = 0;
    this.setState({ branches: branchesClone });
  }

  /**
    @param {}
    dispatches sticky state to redux to update state
  */
  _setStickHeader = () => {
    const { isSticky, sectionType } = this.props;
    const { owner, name } = this.props[sectionType];
    const sticky = 50;
    const isPageOffsetAtThreshold = window.pageYOffset >= sticky;

    this.offsetDistance = window.pageYOffset;
    if (isSticky !== isPageOffsetAtThreshold) {
      setStickyState(owner, name, window.pageYOffset >= sticky);
    }

    if (isSticky) {
      setMergeMode(owner, name, false, false);
    }
  }

  /**
    @param {Boolean} branchesOpen
    @param {Boolean} mergeFilter
    updates branchOpen state
  */
  _toggleBranchesView = (branchesOpen, mergeFilter) => {
    const { sectionType } = this.props;
    const { owner, name } = this.props[sectionType];
    if (store.getState().containerStatus.status !== 'Running') {
      setMergeMode(owner, name, branchesOpen, mergeFilter);
    } else {
      setContainerMenuWarningMessage('Stop Project before switching branches. \n Be sure to save your changes.');
    }
  }

  /**
    @param {}
    updates branchOpen state
  */
  _toggleMigrationModal = () => {
    this.setState((state) => {
      const migrationModalVisible = !state.migrationModalVisible;
      return { migrationModalVisible };
    });
  }

  /**
    scrolls to top of window
    @return {boolean, string}
  */
  _getMigrationInfo = () => {
    const { props, state } = this;
    const isOwner = (localStorage.getItem('username') === props.labbook.owner);
    const {
      isDeprecated,
      shouldMigrate,
    } = state;
    const isPublished = typeof props.labbook.defaultRemote === 'string';

    let migrationText = '';
    let showMigrationButton = false;

    if ((isOwner && isDeprecated && shouldMigrate && isPublished)
        || (isDeprecated && !isPublished && shouldMigrate)) {
      migrationText = 'This Project needs to be migrated to the latest Project format';
      showMigrationButton = true;
    } else if (!isOwner && isDeprecated && shouldMigrate && isPublished) {
      migrationText = 'This Project needs to be migrated to the latest Project format. The project owner must migrate and sync this project to update.';
    } else if ((isDeprecated && !isPublished && !shouldMigrate)
      || (isDeprecated && isPublished && !shouldMigrate)) {
      migrationText = 'This project has been migrated. Master is the new primary branch. Old branches should be removed.';
    }

    return { showMigrationButton, migrationText };
  }

  /**
  * @param {Object} state
  * allows child component to update state
  */
  _setState = (state) => {
    this.setState(state);
  }

  // TODO move migration code into it's own component
  render() {
    const {
      activityRecords,
      auth,
      branchesOpen,
      detailMode,
      diskLow,
      isBuilding,
      isPublishing,
      isSyncing,
      isSticky,
      labbook,
      labbookName,
      match,
      sidePanelVisible,
    } = this.props;
    const { owner, name } = labbook;
    const isLocked = isBuilding
      || isSyncing
      || isPublishing
      || this.state.isLocked;

    if (labbook) {
      const {
        branches,
        branchMutations,
        buttonState,
        canManageCollaborators,
        collaborators,
        isDeprecated,
        lockFileBrowser,
        migrateComplete,
        migrationInProgress,
        migrationModalVisible,
        packageLatestVersions,
      } = this.state;
      const isSidePanelVisible = !isLocked && sidePanelVisible;
      const branchName = '';
      const { migrationText, showMigrationButton } = this._getMigrationInfo();
      const { containerStatus, imageStatus } = labbook.environment;
      // declare css here
      const labbookCSS = classNames({
        Labbook: true,
        'Labbook--detail-mode': detailMode,
        'Labbook--branch-mode': branchesOpen,
        'Labbook--disk-low': diskLow,
        'Labbook--deprecated': isDeprecated,
        'Labbook--disk-low--deprecated': isDeprecated && diskLow,
        'Labbook--sidePanelVisible': isSidePanelVisible,
        'Labbook--locked': isLocked,
      });
      const deprecatedCSS = classNames({
        Labbook__deprecated: true,
        'Labbook__deprecated--disk-low': diskLow,
      });
      const migrationButtonCSS = classNames({
        'Tooltip-data': isLocked,
      });

      return (
        <div className={labbookCSS}>
          <div id="labbook__cover" className="Labbook__cover hidden">
            <Loader />
          </div>
          <div className="Labbook__spacer flex flex--column">
            { isDeprecated
              && (
              <div className={deprecatedCSS}>
                {migrationText}
                <a
                  target="_blank"
                  href="https://docs.gigantum.com/docs/project-migration"
                  rel="noopener noreferrer"
                >
                  Learn More.
                </a>
                {
                  showMigrationButton
                  && (
                  <div
                    className={migrationButtonCSS}
                    data-tooltip="To migrate the project container must be Stopped."
                  >
                    <button
                      className="Button Labbook__deprecated-action"
                      onClick={() => this._toggleMigrationModal()}
                      disabled={migrationInProgress || isLocked}
                      type="button"
                    >
                      Migrate
                    </button>
                  </div>
                  )
                }
              </div>
              )
            }

            <MigrationModal
              branchMutations={branchMutations}
              buttonState={buttonState}
              labbook={labbook}
              migrationModalVisible={migrationModalVisible}
              migrateComplete={migrateComplete}
              setParentState={this._setState}
              toggleMigrationModal={this._toggleMigrationModal}
            />

            <Header
              {...this.props}
              owner={owner}
              name={name}
              ref={header => header}
              description={labbook.description}
              toggleBranchesView={this._toggleBranchesView}
              sectionType="labbook"
              containerStatus={containerStatus}
              imageStatus={imageStatus}
              isLocked={isLocked}
              isSticky={isSticky}
              collaborators={collaborators}
              canManageCollaborators={canManageCollaborators}
              visibility={labbook.visibility}
              defaultRemote={labbook.defaultRemote}
              branches={branches}
              setBranchUptodate={this._setBranchUptodate}
              isDeprecated={isDeprecated}
              updateMigationState={this._updateMigationState}
              sidePanelVisible={isSidePanelVisible}
              showMigrationButton={showMigrationButton}
            />
            <div className="Labbook__routes flex flex-1-0-auto">
              <Switch>
                <Route
                  exact
                  path={`${match.path}`}
                  render={() => (
                    <ErrorBoundary type="labbookSectionError">
                      <Overview
                        {...this.props}
                        key={`${labbookName}_overview`}
                        labbook={labbook}
                        labbookId={labbook.id}
                        refetch={this._refetchSection}
                        isPublishing={isPublishing}
                        scrollToTop={scrollToTop}
                        sectionType="labbook"
                        owner={owner}
                        name={name}
                      />
                    </ErrorBoundary>
                  )}
                />

                <Route path={`${match.path}/:labbookMenu`}>

                  <Switch>

                    <Route
                      path={`${match.path}/overview`}
                      render={() => (

                        <ErrorBoundary
                          type="labbookSectionError"
                          key="overview"
                        >
                          <Overview
                            {...this.props}
                            key={`${labbookName}_overview`}
                            labbook={labbook}
                            description={labbook.description}
                            labbookId={labbook.id}
                            refetch={this._refetchSection}
                            isPublishing={isPublishing}
                            scrollToTop={scrollToTop}
                            sectionType="labbook"
                            owner={owner}
                            name={name}
                          />
                        </ErrorBoundary>
                      )}
                    />

                    <Route
                      path={`${match.path}/activity`}
                      render={() => (
                        <ErrorBoundary
                          type="labbookSectionError"
                          key="activity"
                        >
                          <Activity
                            {...this.props}
                            key={`${labbookName}_activity`}
                            labbook={labbook}
                            diskLow={diskLow}
                            refetch={this._refetchSection}
                            activityRecords={activityRecords}
                            labbookId={labbook.id}
                            branchName={branchName}
                            description={labbook.description}
                            activeBranch={labbook.activeBranchName}
                            isMainWorkspace={branchName === 'master'}
                            sectionType="labbook"
                            isLocked={isLocked}
                            isDeprecated={isDeprecated}
                            owner={owner}
                            name={name}
                          />
                        </ErrorBoundary>
                      )}
                    />

                    <Route
                      path={`${match.url}/environment`}
                      render={() => (
                        <ErrorBoundary
                          type="labbookSectionError"
                          key="environment"
                        >
                          <Environment
                            {...this.props}
                            key={`${labbookName}_environment`}
                            labbook={labbook}
                            owner={owner}
                            name={name}
                            labbookId={labbook.id}
                            refetch={this._refetchSection}
                            overview={labbook.overview}
                            isLocked={isLocked}
                            packageLatestVersions={packageLatestVersions}
                            packageLatestRefetch={this._packageLatestRefetch}
                            cancelRefetch={this._cancelRefetch}
                          />
                        </ErrorBoundary>
                      )}
                    />

                    <Route
                      path={`${match.url}/code`}
                      render={() => (
                        <ErrorBoundary
                          type="labbookSectionError"
                          key="code"
                        >
                          <Code
                            labbook={labbook}
                            labbookId={labbook.id}
                            refetch={this._refetchSection}
                            setContainerState={this._setContainerState}
                            isLocked={isLocked}
                            containerStatus={containerStatus}
                            section="code"
                            lockFileBrowser={lockFileBrowser}
                            owner={labbook.owner}
                            name={labbook.name}
                          />

                        </ErrorBoundary>
                      )}
                    />

                    <Route
                      path={`${match.url}/inputData`}
                      render={() => (
                        <ErrorBoundary
                          type="labbookSectionError"
                          key="input"
                        >
                          <InputData
                            labbook={labbook}
                            labbookId={labbook.id}
                            isLocked={isLocked}
                            refetch={this._refetchSection}
                            containerStatus={containerStatus}
                            lockFileBrowser={lockFileBrowser}
                            owner={labbook.owner}
                            name={labbook.name}
                            section="input"
                          />
                        </ErrorBoundary>
                      )}
                    />

                    <Route
                      path={`${match.url}/outputData`}
                      render={() => (
                        <ErrorBoundary
                          type="labbookSectionError"
                          key="output"
                        >
                          <OutputData
                            labbook={labbook}
                            labbookId={labbook.id}
                            isLocked={isLocked}
                            refetch={this._refetchSection}
                            containerStatus={containerStatus}
                            lockFileBrowser={lockFileBrowser}
                            owner={labbook.owner}
                            name={labbook.name}
                            section="output"
                          />
                        </ErrorBoundary>
                      )}
                    />

                  </Switch>

                </Route>

              </Switch>

            </div>

          </div>
          <div className="Labbook__veil" />
        </div>
      );
    }
    const { authenticated } = this.state;
    if (authenticated) {
      return (<Loader />);
    }

    return (<Login auth={auth} />);
  }
}

const mapStateToProps = (state, props) => {
  const { owner, name } = props.labbook;
  const namespace = `${owner}_${name}`;
  const namespaceState = state.labbook[namespace]
    ? state.labbook[namespace]
    : state.labbook;

  const { isUploading } = state.labbook;
  return {
    ...namespaceState,
    globalIsUploading: isUploading,
    owner,
    name,
  };
};

const mapDispatchToProps = () => ({ setBuildingState });

const LabbookContainer = connect(mapStateToProps, mapDispatchToProps)(Labbook);


const LabbookFragmentContainer = createRefetchContainer(
  LabbookContainer,
  {
    labbook: graphql`
      fragment Labbook_labbook on Labbook {
          id
          description
          defaultRemote
          owner
          name
          visibility @skip(if: $labbookSkip)
          activeBranchName

          environment{
            containerStatus
            imageStatus
            base{
              developmentTools
            }
          }

         branches {
           id
           owner
           name
           branchName
           isActive
           isLocal
           isRemote
         }
         environment {
           bundledApps {
             appName
           }
         }
          ...Environment_labbook
          ...LabbookOverviewContainer_labbook
          ...LabbookActivityContainer_labbook
          ...Code_labbook
          ...Input_labbook
          ...Output_labbook

      }`,
  },
  graphql`
  query LabbookRefetchQuery($first: Int!, $cursor: String, $skipPackages: Boolean!, $labbookID: ID!, $environmentSkip: Boolean!, $overviewSkip: Boolean!, $activitySkip: Boolean!, $codeSkip: Boolean!, $inputSkip: Boolean!, $outputSkip: Boolean!, $labbookSkip: Boolean!){
    labbook: node(id: $labbookID){
      ... on Labbook {
        visibility @skip(if: $labbookSkip)
      }
      ...Environment_labbook
      ...LabbookOverviewContainer_labbook
      ...LabbookActivityContainer_labbook
      ...Code_labbook
      ...Input_labbook
      ...Output_labbook
    }
  }
  `,
);


export default DragDropContext(backend)(LabbookFragmentContainer);
