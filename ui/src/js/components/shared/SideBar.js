import React, { Component } from 'react';
import classNames from 'classnames';
import { Link } from 'react-router-dom';
// components
import User from './User';
import ToolTip from 'Components/shared/ToolTip';
// store
import { setCallbackRoute } from 'JS/redux/reducers/routes';
// config
import config from 'JS/config';

export default class SideBar extends Component {
  constructor(props) {
    super(props);
    this.state = {
      authenticated: null,
    };
  }
  /*
    sets authentication response to the state
  */
  componentDidMount() {
    this.props.auth.isAuthenticated().then((response) => {
      let isAuthenticated = response;
      if (isAuthenticated === null) {
        isAuthenticated = false;
      }
      if (response !== this.state.authenticated) {
        this.setState({ authenticated: isAuthenticated });
      }
    });
  }
  /**
    @param {}
    logout through Auth0
  */
  logout() {
    this.props.auth.logout();
  }
  render() {
    const isLabbooks = (window.location.href.indexOf('labbooks') > 0) || (window.location.href.indexOf('datsets') === -1);
    const sidebarCSS = classNames({
      'SideBar col-sm-1': this.state.authenticated || this.state.authenticated === null,
      hidden: !(this.state.authenticated || this.state.authenticated === null),
      'is-demo': window.location.hostname === config.demoHostName,
    });
    return (
      <div className={sidebarCSS}>
        <div className="SideBar__inner-container">
          <div className="SideBar__logo" />
          <ul className="SideBar__nav">
            <li className={isLabbooks ? 'SideBar__list-item--selected' : 'SideBar__list-item'}>
              <Link
                onClick={() => setCallbackRoute('/projects/local')}
                className={isLabbooks ? 'SideBar__nav-item SideBar__nav-item--labbooks SideBar__nav-item--selected' : 'SideBar__nav-item SideBar__nav-item--labbooks'}
                to={{ pathname: '/projects/local' }}
              >
                <div className={isLabbooks ? 'SideBar__icon SideBar__icon--labbooks-selected' : 'SideBar__icon SideBar__icon--labbooks'} />
                Projects
              </Link>
              <ToolTip section="labbookListing" />
            </li>
            <li className={!isLabbooks ? 'SideBar__list-item--selected' : 'SideBar__list-item'}>
              <div
                className={!isLabbooks ? 'SideBar__nav-item SideBar__nav-item--datasets SideBar__nav-item--selected' : 'SideBar__nav-item SideBar__nav-item--datasets'}
                to={{ pathname: '/datasets' }}
              >
                <div className={!isLabbooks ? 'SideBar__icon SideBar__icon--datasets-selected' : 'SideBar__icon SideBar__icon--datasets'} />
                Datasets
              </div>
              <ToolTip section="dataSets" />
            </li>
          </ul>

          {
            this.state.authenticated && (
            <User {...this.props} />
              )
          }
        </div>
      </div>
    );
  }
}
