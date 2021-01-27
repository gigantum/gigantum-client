// @flow
// vendor
import React, { Component } from 'react';
import classNames from 'classnames';
// components
import PopupBlocked from 'Components/modal/popup/PopupBlocked';
// store
import { setMergeMode, updateTransitionState } from 'JS/redux/actions/labbook/labbook';
import { setErrorMessage, setInfoMessage, setWarningMessage } from 'JS/redux/actions/footer';
// assets
import './DevTools.scss';

const getDevTool = (project) => {
  let devTools = project.environment.base
    ? project.environment.base.developmentTools
    : [];
  const bundledApps = Object.keys(project.environment.bundledApps).map(index => {
    return project.environment.bundledApps[index].appName;
  });
  devTools = devTools.concat(bundledApps);
  devTools = devTools.filter(tool => !(tool === 'rstudio' && process.env.BUILD_TYPE === 'cloud'));
  return {
    devTools,
    bundledApps,
  };
};

const setSelectedDevTool = (self) => {
  const { labbook } = self.props;
  const { owner, name, environment } = labbook;
  const defaultFromApi = environment.base
    ? environment.base.developmentTools[0]
    : 'jupyterlab';
  const devToolConfig = localStorage.getItem('devToolConfig')
    ? JSON.parse(localStorage.getItem('devToolConfig'))
    : {};

  if (devToolConfig._timestamps && devToolConfig._timestamps[0]) {
    const oldestConfig = devToolConfig._timestamps[0].time;
    const timeStampedOwner = devToolConfig._timestamps[0].owner;
    const timeStampedName = devToolConfig._timestamps[0].name;
    const threeMonthsAgo = (new Date()).setMonth(new Date().getMonth() - 3);
    if (threeMonthsAgo > oldestConfig) {
      if (devToolConfig[timeStampedOwner] && devToolConfig[timeStampedOwner][timeStampedName]) {
        delete devToolConfig[timeStampedOwner][timeStampedName];
      }
      if (devToolConfig[timeStampedOwner] && Object.keys(devToolConfig[timeStampedOwner]).length === 0) {
        delete devToolConfig[timeStampedOwner];
      }
      devToolConfig._timestamps.shift();
      localStorage.setItem('devToolConfig', JSON.stringify(devToolConfig));
    }
  }
  if (devToolConfig[owner] && devToolConfig[owner][name]) {
    const { developmentTools } = environment.base;
    const devToolExists = developmentTools.indexOf(devToolConfig[owner][name]) > -1;
    if (devToolExists) {
      return devToolConfig[owner][name];
    }
    delete devToolConfig[owner][name];
    localStorage.setItem('devToolConfig', JSON.stringify(devToolConfig));
  }
  return defaultFromApi;
};


type Props = {
  containerMutations: {
    startContainer: Function,
    startDevTool: Function,
  },
  containerStatus: string,
  creationDateUtc: string,
  imageStatus: string,
  isBuilding: boolean,
  isExporting: boolean,
  isPublishing: boolean,
  isSyncing: boolean,
  labbook: {
    name: string,
    owner: string,
    environment: {
      base: {
        developmentTools: Array,
      }
    }
  },
}

class DevTools extends Component<Props> {
  state = {
    selectedDevTool: setSelectedDevTool(this),
    showDevList: false,
    showPopupBlocked: false,
  }

  static getDerivedStateFromProps(props, state) {
    const { owner, name, environment } = props.labbook;
    const devToolConfig = localStorage.getItem('devToolConfig') ? JSON.parse(localStorage.getItem('devToolConfig')) : {};
    if (devToolConfig[owner] && devToolConfig[owner][name]) {
      const { developmentTools } = environment.base;
      const selectedDevTool = (developmentTools.indexOf(devToolConfig[owner][name]) > -1)
        ? devToolConfig[owner][name]
        : developmentTools[0];
      return {
        ...state,
        selectedDevTool,
      };
    }

    return {
      ...state,
    };
  }

  componentDidMount() {
    window.addEventListener('click', this._closeDevtoolMenu);
  }

  componentWillUnmount() {
    window.removeEventListener('click', this._closeDevtoolMenu);
  }

  /**
   * sets state for popup modal
   */
  _togglePopupModal = () => {
    this.setState({ showPopupBlocked: false });
  }

  /**
  *  @param {Object} evt
  *  closes dev tool
  *  @return {}
  */
  _closeDevtoolMenu = (evt) => {
    if (evt.target.className.indexOf('DevTool') < 0) {
      this.setState({ showDevList: false });
    }
  }

  /**
  *  @param {}
  *  upodates state if the conditions are met
  *  @return {}
  */
  _toggleDevtoolMenu = () => {
    this.setState((state) => {
      const showDevList = !state.showDevList;
      return { showDevList };
    });
  }

  /**
  *  @param {string} developmentTool
  *  @param {string} developmentTool
  *  mutation to trigger opening of development tool
  *  @return {}
  */
  _openDevToolMuation = (developmentTool) => {
    const {
      creationDateUtc,
      containerMutations,
      containerStatus,
      imageStatus,
      labbook,
      isBuilding,
      isExporting,
      isPublishing,
      isSyncing,
    } = this.props;

    const { showPopupBlocked } = this.state;

    const { owner, name } = labbook;
    const labbookCreationDate = Date.parse(`${creationDateUtc}Z`);
    const timeNow = Date.parse(new Date());
    const timeDifferenceMS = timeNow - labbookCreationDate;

    let tabName = `${developmentTool}-${owner}-${name}`;
    let status = (containerStatus === 'RUNNING') ? 'Running' : containerStatus;
    status = (containerStatus === 'NOT_RUNNING') ? 'Stopped' : status;
    status = (imageStatus === 'BUILD_IN_PROGRESS' || imageStatus === 'BUILD_QUEUED') ? 'Building' : status;
    status = (imageStatus === 'BUILD_FAILED') ? 'Rebuild' : status;
    status = (imageStatus === 'DOES_NOT_EXIST') ? 'Rebuild' : status;
    status = ((imageStatus === 'DOES_NOT_EXIST') || (imageStatus === 'BUILD_IN_PROGRESS')) && (timeDifferenceMS < 15000) ? 'Building' : status;

    if (
      ((status !== 'Stopped') && (status !== 'Running'))
      || (isExporting || isPublishing || isSyncing || isBuilding)
    ) {
      setWarningMessage(owner, name, 'Could not launch development environment as the project is not ready.');
    } else if (status === 'Stopped') {
      setInfoMessage(owner, name, 'Starting Project container. When done working, click Stop to shutdown the container.');
      setMergeMode(owner, name, false, false);
      updateTransitionState(owner, name, 'Starting');

      containerMutations.startContainer(
        { devTool: developmentTool },
        (response, error) => {
          if (error) {
            setErrorMessage(owner, name, 'Error Starting Dev tool', error);
          }

          if (response.startDevTool) {
            tabName = `${developmentTool}-${owner}-${name}`;
            let path = `${window.location.protocol}//${window.location.hostname}${response.startDevTool.path}`;
            if (developmentTool === 'notebook') {
              if (path.includes('/lab/tree')) {
                path = path.replace('/lab/tree', '/tree');
              } else {
                path = `${path}/tree/code`;
              }
            }

            window[tabName] = window.open(path, tabName);
            if (
              !window[tabName]
              || window[tabName].closed
              || typeof window[tabName].closed === 'undefined'
            ) {
              this.setState({ showPopupBlocked: true });
            } else if (showPopupBlocked) {
              this.setState({ showPopupBlocked: false });
            }
          }
        },
      );
    } else if (window[tabName] && !window[tabName].closed) {
      window[tabName].focus();
    } else {
      const data = { devTool: developmentTool };
      setInfoMessage(owner, name, `Starting ${developmentTool}, make sure to allow popups.`);

      containerMutations.startDevTool(
        data,
        (response, error) => {
          if (response.startDevTool) {
            tabName = `${developmentTool}-${owner}-${name}`;
            let path = `${window.location.protocol}//${window.location.hostname}${response.startDevTool.path}`;
            if (developmentTool === 'notebook') {
              if (path.includes('/lab/tree')) {
                path = path.replace('/lab/tree', '/tree');
              } else {
                path = `${path}/tree/code`;
              }
            }

            window[tabName] = window.open(path, tabName);
            if (
              !window[tabName]
              || window[tabName].closed
              || typeof window[tabName].closed === 'undefined'
            ) {
              this.setState({ showPopupBlocked: true });
            } else if (showPopupBlocked) {
              this.setState({ showPopupBlocked: false });
            }
          }

          if (error) {
            setErrorMessage(owner, name, 'Error Starting Dev tool', error);
          }
        },
      );
    }
  }

  /**
  *  @param {string} developmentTool
  *  mutation to trigger opening of development tool
  *  @return {}
  */
  _selectDevTool = (developmentTool) => {
    const { labbook } = this.props;
    const { owner, name } = labbook;
    const devToolConfig = localStorage.getItem('devToolConfig')
      ? JSON.parse(localStorage.getItem('devToolConfig'))
      : {};
    const ownerObject = devToolConfig[owner] || {};
    const newObject = {
      [owner]: {
        ...ownerObject,
        [name]: developmentTool,
      },
    };
    const newDevToolConfig = Object.assign({}, devToolConfig, newObject);
    if (newDevToolConfig._timestamps) {
      newDevToolConfig._timestamps.push({ time: (new Date()).getTime(), owner, name });
    } else {
      newDevToolConfig._timestamps = [{ time: (new Date()).getTime(), owner, name }];
    }
    localStorage.setItem('devToolConfig', JSON.stringify(newDevToolConfig));

    this.setState({ selectedDevTool: developmentTool, showDevList: false });
    this._openDevToolMuation(developmentTool);
  }

  render() {
    const { labbook } = this.props;
    const {
      selectedDevTool,
      showDevList,
      showPopupBlocked,
    } = this.state;
    let {
      devTools,
      bundledApps,
    } = getDevTool(labbook);
    devTools = devTools.filter(tool => !(tool === 'rstudio' && process.env.BUILD_TYPE === 'cloud'));
    const disableLaunch = process.env.BUILD_TYPE === 'cloud'
      && selectedDevTool === 'rstudio';
    // declare css here
    const devtToolMenuCSS = classNames({
      'DevTools__dropdown-menu': true,
      hidden: !showDevList,
    });
    const buttonDropdownCSS = classNames({
      'DevTools__btn DevTools__btn--dropdown': true,
      'DevTools__btn--open': showDevList,
    });
    const launchCSS = classNames({
      'DevTools__btn DevTools__btn--launch Btn--columns Btn-last': true,
      'Tooltip-data': disableLaunch,
    });

    return (
      <div className="DevTools">
        {
          showPopupBlocked
          && (
            <PopupBlocked
              togglePopupModal={this._togglePopupModal}
              devTool={selectedDevTool}
              attemptRelaunch={() => { this._openDevToolMuation(selectedDevTool); }}
            />
          )
        }
        <div className="DevTools__flex">
          <button
            type="submit"
            className={launchCSS}
            onClick={() => { this._openDevToolMuation(selectedDevTool); }}
            disabled={disableLaunch}
            data-tooltip="Rstudio launching is currently only available using Gigantum Desktop"
          >
            <div className="Btn--label">Launch:</div>
            <div className="Btn--text">{selectedDevTool}</div>
          </button>

          <button
            type="button"
            data-id="DevToolDropdown"
            className={buttonDropdownCSS}
            onClick={evt => this._toggleDevtoolMenu(evt)}
          />

        </div>

        <div className={devtToolMenuCSS}>
          <div className="DevTool__menu-title">Launch</div>
          <ul className="DevTool__list">
            {

                devTools.map((developmentTool) => {
                  const devToolsCss = classNames({
                    DevTools__item: true,
                    'DevTools__item--selected': (developmentTool === selectedDevTool),
                    'DevTools__item--custom': (bundledApps.indexOf(developmentTool) > -1),
                  });

                  return (
                    <li
                      role="presentation"
                      key={developmentTool}
                      className={devToolsCss}
                      onClick={() => this._selectDevTool(developmentTool)}
                    >
                      <div className="DevTools__icon jupyter-icon" />
                      <div className="DevTools__text">{developmentTool}</div>
                    </li>
                  );
                })
              }
          </ul>
        </div>
      </div>
    );
  }
}

export default DevTools;
