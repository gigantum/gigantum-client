// @flow
// vendor
import React, { Component } from 'react';
import Loadable from 'react-loadable';
import { connect } from 'react-redux';
import queryString from 'querystring';
import {
  Router,
  Route,
  Switch,
  Redirect,
} from 'react-router-dom'; // keep browser router, reloads page with Router in labbook view
// components
import Layout from 'JS/layout/Layout';
import Dashboard from 'Pages/dashboard/Dashboard';
import Login from 'Pages/login/Login';
// queries
import AppQuery from 'JS/Auth/App';
// store
import { setBaseUrl } from 'JS/redux/actions/routes';
// utils
import getApiURL from 'JS/utils/apiUrl';
// assets
import './Routes.scss';

const Loading = () => <div />;

/* eslint-disable */
const globalObject = window || self;
/* eslint-enable */

const LabbookQueryContainer = Loadable({
  loader: () => import('Pages/repository/labbook/LabbookQueryContainer'),
  loading: Loading,
});

const DatasetQueryContainer = Loadable({
  loader: () => import('Pages/repository/dataset/DatasetQueryContainer'),
  loading: Loading,
});

// getter functions
const getBasename = () => {
  const { pathname } = globalObject.location;
  const pathList = pathname.split('/');
  const uniqueClientString = (pathList.length > 2)
    ? pathList[2]
    : '';
  const basename = process.env.BUILD_TYPE === 'cloud'
    ? `/run/${uniqueClientString}/`
    : '/';
  return basename;
};

class Routes extends Component {
  state = {
    hasError: false,
    forceLoginScreen: null,
    diskLow: false,
    serverName: '',
  };

  basename = getBasename();

  componentDidMount() {
    const { history } = this.props;
    const values = queryString.parse(history.location.hash.slice(1));
    const newPath = values.path;

    if (newPath) {
      delete values.path;
      values.redirect = false;
      let stringifiedValues = queryString.stringify(values);
      history.replace(`${this.basename}${newPath}#${stringifiedValues}`);
      delete values.redirect;
      stringifiedValues = queryString.stringify(values);
      window.location.hash = stringifiedValues;
    }

    this._checkSysinfo();

    AppQuery.getAppData().then((response) => {
      if (
        response.data
        && response.data.currentServer
      ) {
        const { currentServer } = response.data;
        setBaseUrl(currentServer.baseUrl);
        this.setState({ serverName: currentServer.name });
      }
    });
  }

  /**
    @param {}
    calls flip header text function
  */


  /**
    @param{}
    logs user out in using auth0
  */
  login = () => {
    const { auth } = this.props;
    auth.login();
  }

  /**
    @param{}
    logs user out using auth0
  */
  logout = () => {
    const { auth } = this.props;
    auth.logout();
  }

  /**
    @param {boolean} forceLoginScreen
    sets state of forceloginscreen
  */
  _setForceLoginScreen = (forceLoginScreen) => {
    const { state } = this;
    if (forceLoginScreen !== state.forceLoginScreen) {
      this.setState({ forceLoginScreen });
    }
  }

  /**
    hides disk warning
  */
  _hideDiskWarning = () => {
    window.sessionStorage.setItem('hideDiskWarning', true);
    this.forceUpdate();
  }

  /**
    shows sysinfo header if available size is too small
  */
  _checkSysinfo = () => {
    // TODO move to utils file
    const self = this;
    const apiURL = getApiURL('sysinfo');
    setTimeout(self._checkSysinfo.bind(this), 60 * 1000);
    return fetch(apiURL, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
        accept: '*/*',
      },
    }).then((response) => {
      if (response.status === 200 && (response.headers.get('content-type') === 'application/json')) {
        response.json().then((res) => {
          const { available, lowDiskWarning } = res.diskGb;
          self.setState({ diskLow: lowDiskWarning, available });
        });
      }
    }).catch(() => false);
  }

  /**
    @param {Error, Object} error, info
    shows error message when runtime error occurs
  */
  componentDidCatch() {
    this.setState({ hasError: true });
  }

  render() {
    const { props, state } = this;
    const {
      auth,
      baseUrl,
      history,
      isLoggedIn,
    } = this.props;
    const { serverName } = this.state;
    const showDiskLow = state.diskLow && !window.sessionStorage.getItem('hideDiskWarning');

    if (!state.hasError) {
      // declare csc

      return (

        <Router
          history={history}
          basename={this.basename}
        >
         <Layout
            auth={auth}
            baseUrl={baseUrl}
            diskLow={showDiskLow}
            history={history}
          >

          <Switch>

            <Route
              exact
              path={[
                '/',
                '/datasets/:labbookSection',
                '/projects/:labbookSection',
              ]}
              render={parentProps => (
                <Dashboard
                  {...props}
                  {...parentProps}
                  auth={auth}
                  baseUrl={baseUrl}
                  diskLow={showDiskLow}
                  history={history}
                  serverName={serverName}
                />
              )
              }
            />

            <Route
              exact
              path={[
                '/labbooks/:section',
                '/:id',
              ]}
              render={() => <Redirect to="/projects/local" />}
            />

            <Route
              path="/datasets/:owner/:datasetName"
              auth={auth}
              render={(parentProps) => (
                <DatasetQueryContainer
                  {...props}
                  {...parentProps}
                  auth={auth}
                  baseUrl={baseUrl}
                  datasetName={parentProps.match.params.datasetName}
                  diskLow={showDiskLow}
                  history={history}
                  owner={parentProps.match.params.owner}
                  serverName={serverName}
                />
               )}
              />

              <Route
                path="/projects/:owner/:labbookName"
                auth={auth}
                render={(parentProps) => (
                  <LabbookQueryContainer
                    {...props}
                    {...parentProps}
                    auth={auth}
                    baseUrl={baseUrl}
                    diskLow={showDiskLow}
                    history={history}
                    labbookName={parentProps.match.params.labbookName}
                    owner={parentProps.match.params.owner}
                    serverName={serverName}
                  />
                 )}
               />
            </Switch>
          </Layout>
        </Router>
      );
    }

    return (
      <div className="Routes__error">
        <p>An error has occured. Please try refreshing the page.</p>
      </div>
    );
  }
}

const mapStateToProps = state => state.routes;

const mapDispatchToProps = () => ({});

export default connect(mapStateToProps, mapDispatchToProps)(Routes);
