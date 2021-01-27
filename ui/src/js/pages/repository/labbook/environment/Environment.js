// vendor
import React, { Component } from 'react';
import { createFragmentContainer, graphql } from 'react-relay';
import classNames from 'classnames';
import { connect } from 'react-redux';
// store
import { setErrorMessage } from 'JS/redux/actions/footer';
import { setBuildingState } from 'JS/redux/actions/labbook/labbook';
import { toggleAdvancedVisible } from 'JS/redux/actions/labbook/environment/environment';
import store from 'JS/redux/store';
// mutations
import BuildImageMutation from 'Mutations/container/BuildImageMutation';
import StopContainerMutation from 'Mutations/container/StopContainerMutation';
// components
import ErrorBoundary from 'Components/errorBoundary/ErrorBoundary';
import Tooltip from 'Components/tooltip/Tooltip';
import Loader from 'Components/loader/Loader';
import Base from './Base';
import Packages from './packages/Packages';
import Secrets from './secrets/Secrets';
import CustomApps from './customApps/CustomApps';
import CustomDockerfile from './CustomDockerfile';
// assets
import './Environment.scss';


const buildImage = (owner, name, buildData, callback) => {
  BuildImageMutation(
    owner,
    name,
    buildData,
    (response, error, id) => {
      if (error) {
        setErrorMessage(owner, name, `${name} failed to build`, error);
      }
      if (callback) {
        callback(response, error, id);
      }

      return 'finished';
    },
  );
};

type Props = {
  owner: string,
  name: string,
  labbook: {
    environment: {
      id: string,
      base: {
         id: string,
      },
      bundledApps: Array,
    }
  },
  containerStatus: string,
  advancedVisible: bool,
  isLocked: bool,
  overview: Object,
  packageLatestVersions: string,
  packageLatestRefetch: string,
  cancelRefetch: bool,
  advancedVisible: bool,
}

class Environment extends Component<Props> {
  componentDidMount() {
    const { props } = this;
    props.refetch('environment');
  }

  /**
  *  @param {Function} callback
  *  callback that triggers buildImage mutation
  */
  _buildCallback = (callback) => {
    const { name, owner } = this.props;
    let buildData = false;
    if (callback) {
      buildData = {
        hideFooter: true,
      };
    }

    setBuildingState(owner, name, true);

    if (store.getState().containerStatus.status === 'Running') {
      StopContainerMutation(
        owner,
        name,
        (response, error) => {
          if (error) {
            console.log(error);
            setErrorMessage(owner, name, `Problem stopping ${name}`, error);
          } else {
            buildImage(
              owner,
              name,
              buildData,
              callback,
            );
          }
        },
      );
    } else {
      buildImage(
        owner,
        name,
        buildData,
        callback,
      );
    }
  }

  render() {
    const {
      advancedVisible,
      labbook,
      containerStatus,
      isLocked,
      owner,
      name,
      overview,
      packageLatestVersions,
      packageLatestRefetch,
      cancelRefetch,
    } = this.props;
    // declare css here
    const advancedCSS = classNames({
      'Btn Btn__advanced Btn--action Btn--noShadow': true,
      'Btn__advanced--expanded': advancedVisible,
      'Btn__advanced--collapsed': !advancedVisible,
    });

    if (labbook && labbook.environment && labbook.environment.id) {
      const { environment } = labbook;
      const { base } = environment;
      return (
        <div className="Environment">
          <div className="Base__headerContainer flex">
            <h4>
                Base&nbsp;&nbsp;&nbsp;
              <Tooltip section="baseEnvironment" />
            </h4>
          </div>
          <ErrorBoundary type="baseError" key="base">
            <Base
              environment={environment}
              baseLatestRevision={environment.baseLatestRevision}
              environmentId={environment.id}
              editVisible
              containerStatus={containerStatus}
              setComponent={this._setComponent}
              buildCallback={this._buildCallback}
              blockClass="Environment"
              base={base}
              isLocked={isLocked}
              owner={owner}
              name={name}
            />
          </ErrorBoundary>
          <ErrorBoundary type="packageDependenciesError" key="packageDependencies">
            <Packages
              componentRef={(ref) => { this.packageDependencies = ref; }}
              owner={owner}
              name={name}
              environment={labbook.environment}
              environmentId={labbook.environment.id}
              labbookId={labbook.id}
              containerStatus={containerStatus}
              setComponent={this._setComponent}
              buildCallback={this._buildCallback}
              overview={overview}
              base={base}
              isLocked={isLocked}
              packageLatestVersions={packageLatestVersions}
              packageLatestRefetch={packageLatestRefetch}
              cancelRefetch={cancelRefetch}
            />
          </ErrorBoundary>
          <div className="flex justify--center align-items--center relative column-1-span-12">
            <button
              className={advancedCSS}
              onClick={() => toggleAdvancedVisible(!advancedVisible)}
              type="button"
            >
              Advanced Configuration Settings
              <span />
            </button>
          </div>
          {
            advancedVisible
            && (
              <div>
                <CustomDockerfile
                  dockerfile={labbook.environment.dockerSnippet}
                  buildCallback={this._buildCallback}
                  isLocked={isLocked}
                  owner={owner}
                  name={name}
                />
                <Secrets
                  environment={labbook.environment}
                  environmentId={labbook.environment.id}
                  owner={owner}
                  name={name}
                  isLocked={isLocked}
                />
                <CustomApps
                  customApps={labbook.environment.bundledApps}
                  environmentId={labbook.environment.id}
                  owner={owner}
                  name={name}
                  isLocked={isLocked}
                />
              </div>
            )
          }
        </div>
      );
    }
    return (
      <Loader />
    );
  }
}

const mapStateToProps = state => state.environment;

const mapDispatchToProps = () => ({});

const EnvironmentContainer = connect(mapStateToProps, mapDispatchToProps)(Environment);

export default createFragmentContainer(
  EnvironmentContainer,
  {
    labbook: graphql`fragment Environment_labbook on Labbook {
      environment @skip (if: $environmentSkip){
        id
        imageStatus
        containerStatus
        base{
          developmentTools
          packageManagers
        }
        dockerSnippet
        baseLatestRevision
        bundledApps {
          id
          owner
          name
          appName
          description
          port
          command
        }

        ...Base_environment
        ...Packages_environment
        ...Secrets_environment
      }
    }`,
  },
);
