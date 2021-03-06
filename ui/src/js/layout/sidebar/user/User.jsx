// vendor
import React, { Component } from 'react';
import classNames from 'classnames';
// context
import ServerContext from 'Pages/ServerContext';
// assets
import serverImg from 'Images/icons/server.svg';
import './User.scss';

type Props = {
  auth: {
    logout: Function,
  },
}

class User extends Component<Props> {
  state = {
    username: localStorage.getItem('username') || '',
    dropdownVisible: false,
  };

  componentDidMount() {
    document.addEventListener('mousedown', this._handleClickOutside.bind(this));
  }

  componentWillUnmount() {
    document.removeEventListener('mousedown', this._handleClickOutside.bind(this));
  }

  /**
    Mehtod logs user out using session instance of auth
    @param {} -
  */
  logout = () => {
    const { currentServer } = this.context;
    const { auth } = this.props;
    auth.logout(currentServer);
    localStorage.setItem('fresh_login', true);
    this._toggleDropdown();
  }

  /**
    @param {}
    handles click to update state
  */
  _handleClickOutside = (event) => {
    const { state } = this;
    const userElementIds = ['user', 'username', 'logout', 'profile'];
    if (state.dropdownVisible && (userElementIds.indexOf(event.target.id) < 0)) {
      const dropdownVisible = false;
      this.setState({ dropdownVisible });
    }
  }

  /**
    @param {}
    toggles dropdown state
  */
  _toggleDropdown = () => {
    this.setState((state) => {
      const dropdownVisible = !state.dropdownVisible;
      return {
        ...state,
        dropdownVisible,
      };
    });
  }

  static contextType = ServerContext;

  render() {
    const { dropdownVisible, username } = this.state;
    const { currentServer } = this.context;
    const { baseUrl, name } = currentServer;
    const firstInitial = username.charAt(0).toUpperCase();
    // declare css here
    const usernameCSS = classNames({
      User__name: true,
      'User__name--active': dropdownVisible,
      'User__name--long': username.length >= 10,
    });
    const userDropdownCSS = classNames({
      User__dropdown: true,
      hidden: !dropdownVisible,
    });
    const arrowCSS = classNames({
      'User__dropdown--arrow': true,
      hidden: !dropdownVisible,
    });
    return (
      <div
        id="user"
        className="User"
        key="user"
      >
        <div className="User__server flex flex-row">
          <img
            alt="Server"
            className="User__icon"
            src={serverImg}
          />
          <h6 className="User__server-name">{name}</h6>
        </div>
        <div className="User__image">{firstInitial}</div>
        <h6
          role="presentation"
          id="username"
          onClick={() => { this._toggleDropdown(); }}
          className={usernameCSS}
          data-tooltip={username}
        >
          {username}
        </h6>

        <div className={arrowCSS} />

        <div className={userDropdownCSS}>
          { ((baseUrl === 'https://gigantum.com/')
            || (baseUrl === 'https://gtm-dev.cloud/'))
            && (
              <a
                id="profile"
                href={`${baseUrl}${username}/settings`}
                rel="noopener noreferrer"
                target="_blank"
                className="User__button"
              >
                Profile
              </a>
            )
          }
          {
            (process.env.BUILD_TYPE !== 'cloud')
            && (
              <button
                type="button"
                id="logout"
                className="User__button Btn Btn--flat"
                onClick={this.logout.bind(this)}
              >
                Logout
              </button>
            )
          }
        </div>
      </div>
    );
  }
}

export default User;
