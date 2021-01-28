// @flow
// vendor
import React, { Component } from 'react';
import classNames from 'classnames';
// config
import config from 'JS/config';
import fetchQuery from 'JS/fetch';
// context
import ServerContext from 'Pages/ServerContext';
// components
import ButtonLoader from 'Components/buttonLoader/ButtonLoader';

type Props = {
  canManageCollaborators: boolean,
  collaborators: Array,
  getPermissions: Function,
  mutations: {
    addCollaborator: Function,
  },
  sectionType: string,
}

class CollaboratorSearch extends Component<Props> {
  state = {
    addCollaboratorButtonDisabled: false,
    buttonLoaderAddCollaborator: '',
    colloboratorSearchList: [],
    lookupError: false,
    newCollaborator: '',
    newPermissions: 'readonly',
    selectedIndex: 0,
  }

  componentDidMount() {
    window.addEventListener('click', this._closePermissionsMenu);
  }

  /**
    * @param {} -
    * fires when component unmounts
    * removes added event listeners
  */
  componentWillUnmount() {
    window.removeEventListener('click', this._closePermissionsMenu);
  }


  /**
    *  @param {event} evt
    *  closes permission menu
    *  @return {}
    */
  _closePermissionsMenu = (evt) => {
    if (this.permissionsRef && !this.permissionsRef.contains(evt.target)) {
      this.setState({ permissionMenuOpen: false });
    }
  }


  /**
  *  @param {String} userExpanded
  *  toggles permissionMenuOpen in state or assigns userexpanded a name
  *  @return {}
  */
  _togglePermissionsMenu = () => {
    const { permissionMenuOpen } = this.state;
    const { canManageCollaborators } = this.props;

    if (canManageCollaborators) {
      this.setState({ permissionMenuOpen: !permissionMenuOpen });
    }
  }

  /**
  *  @param {String} newPermissions
  *  assigns new permissions in state
  *  @return {}
  */
  _setPermission = (newPermissions) => {
    this.setState({
      newPermissions,
      permissionMenuOpen: false,
    });
  }

  /**
  *  @param {string} collaborator
  *  queries collaborator api and updates list
  *  @return {}
  */
  _completeColloborator = (collaborator) => {
    if (collaborator) {
      this.collaboratorSearch.value = collaborator.username;

      this.setState({
        newCollaborator: collaborator.username,
        colloboratorSearchList: [],
        selectedIndex: 0,
      });
    }
  }

  /**
  *  @param {event} evt
  *  queries collaborator api and updates list
  *  @return {}
  */
  _getUsers = (evt) => {
    const userInput = evt.target.value;
    const { currentServer } = this.context;

    if (
      (userInput.length > 2)
      && (evt.key !== 'Enter')
      && currentServer.userSearchUrl
    ) {
      const apiURL = evt.target.value.indexOf('@') > 0 ? config.userAPI.getUserEmailQueryString(evt.target.value, currentServer.userSearchUrl) : config.userAPI.getUsersQueryString(evt.target.value, currentServer.userSearchUrl);

      fetchQuery(
        apiURL,
        {},
        { force: true },
      ).then((response, error) => {
        if (response instanceof TypeError) {
          this.setState({ lookupError: true });
          return;
        }
        const collaborators = response.hits.hit.map(hit => hit.fields);

        this.setState({ colloboratorSearchList: collaborators, lookupError: false });
      });
    } else {
      this.setState({ colloboratorSearchList: [] });
    }

    this._handleInputKeys(evt);
  }


  /**
  *  @param {number} -
  *  iterate value of index within the bounds of the array size
  *  @return {}
  */
  _setSelectedIndex = (iterate) => {
    const { state } = this;
    let newSelectedIndex = state.selectedIndex + iterate;

    newSelectedIndex = (newSelectedIndex < 0)
      ? state.colloboratorSearchList.length - 1
      : newSelectedIndex;
    newSelectedIndex = (newSelectedIndex >= this.state.colloboratorSearchList.length)
      ? 0
      : newSelectedIndex;

    this.setState({ selectedIndex: newSelectedIndex });
  }

  /**
  *  @param {event} evt
  *  queries collaborator api and updates list
  *  @return {}
  */
  _handleInputKeys = (evt) => {
    const {
      colloboratorSearchList,
      selectedIndex,
    } = this.state;
    if ((evt.type === 'click') || (evt.key === 'Enter')) {
      if (colloboratorSearchList.length > 0) {
        const collaborator = colloboratorSearchList[selectedIndex];

        this._completeColloborator(collaborator);
      } else {
        this._addCollaborator();
      }
    } else if (evt.key === 'ArrowDown') {
      this._setSelectedIndex(1);
    } else if (evt.key === 'ArrowUp') {
      this._setSelectedIndex(-1);
    } else {
      this.setState({ newCollaborator: evt.target.value });
    }
  }

  /**
  *  @param {String} permissionOverride
  *  @param {String} collaboratorName
  *  sets state of Collaborators
  *  @return {}
  */
  _addCollaborator = () => {
    // TODO: cleanup this function
    const {
      mutations,
    } = this.props;
    const {
      newCollaborator,
      newPermissions,
    } = this.state;

    // waiting for backend updates
    this.setState({
      addCollaboratorButtonDisabled: true,
      buttonLoaderAddCollaborator: 'loading',
    });

    const mutationData = {
      collaboratorName: newCollaborator,
      newPermissions,
    };

    mutations.addCollaborator(
      mutationData,
      (response, error) => {
        this.setState({
          newCollaborator: '',
          addCollaboratorButtonDisabled: false,
        });

        this.collaboratorSearch.value = '';

        if (error) {
          this.setState({ buttonLoaderAddCollaborator: 'error' });
        } else {
          this.setState({ buttonLoaderAddCollaborator: 'finished' });
        }

        setTimeout(() => {
          this.setState({ buttonLoaderAddCollaborator: '' });
        }, 2000);
      },
    );
  }

  static contextType = ServerContext;

  render() {
    const {
      canManageCollaborators,
      collaborators,
      getPermissions,
      sectionType,
    } = this.props;
    const {
      addCollaboratorButtonDisabled,
      buttonLoaderAddCollaborator,
      colloboratorSearchList,
      lookupError,
      newCollaborator,
      newPermissions,
      permissionMenuOpen,
      selectedIndex,
    } = this.state;
    const disableAdd = (canManageCollaborators === false)
      || (collaborators && collaborators.length === 0);
    const collaboratorSearchListSliced = colloboratorSearchList.slice(0, 7);
    const disableAddButton = addCollaboratorButtonDisabled
      || (newCollaborator.length < 3) || disableAdd;
    // declare css here
    const collaboratorSearchCSS = classNames({
      CollaboratorsModal__add: true,
      'CollaboratorsModal__add--disabled': disableAdd,
    });
    const collaboratorInputCSS = classNames({
      'CollaboratorsModal__input--collaborators': true,
      'CollaboratorsModal__input--error': lookupError,
    });
    const autoCompleteMenu = classNames({
      'CollaboratorsModal__auto-compelte-menu box-shadow': true,
      'CollaboratorsModal__auto-compelte-menu--visible': colloboratorSearchList.length > 0,
    });
    const permissionsSelectorCSS = classNames({
      'CollaboratorModal__PermissionsSelector Dropdown': true,
      'Dropdown--open': permissionMenuOpen,
      'CollaboratorModal__PermissionsSelector--add': true,
      'Dropdown--collapsed': !permissionMenuOpen,
    });
    const permissionsMenuCSS = classNames({
      'CollaboratorModal__PermissionsMenu Dropdown__menu box-shadow': true,
      hidden: !permissionMenuOpen,
    });

    return (
      <div className={collaboratorSearchCSS}>
        <div>
          <input
            className={collaboratorInputCSS}
            disabled={disableAdd}
            ref={(ref) => { this.collaboratorSearch = ref; }}
            onChange={evt => this._getUsers(evt)}
            onKeyUp={evt => this._getUsers(evt)}
            type="text"
            placeholder="Add Collaborator"
          />
          { lookupError
            && <p className="CollaboratorModal__p--error">Collaborator lookup failed, try restarting gigantum or contact support.</p>}
        </div>

        <div className={autoCompleteMenu}>

          <ul className="CollaboratorsModal__list">
            { collaboratorSearchListSliced.map((collaborator, index) => {
              const listItemCSS = classNames({
                CollaboratorsModal__listItem: true,
                'CollaboratorsModal__listItem--selected': (index === selectedIndex),
              });
              return (
                <li
                  role="presentation"
                  onClick={() => this._completeColloborator(collaborator)}
                  className={listItemCSS}
                  key={collaborator.username}
                >
                  <div className="CollaboratorsModal__listItem--username">{collaborator.username}</div>
                  <div className="CollaboratorsModal__listItem--name">{collaborator.name}</div>
                </li>
              );
            })}
          </ul>

        </div>

        <div
          className="CollaboratorsModal__permissions"
          ref={(ref) => { this.permissionsRef = ref; }}
        >

          <span
            role="presentation"
            className={permissionsSelectorCSS}
            onClick={() => this._togglePermissionsMenu()}
          >
            {getPermissions(newPermissions)}
          </span>

          <ul className={permissionsMenuCSS}>

            <li
              role="presentation"
              onClick={() => this._setPermission('readonly')}
            >
              <div className="CollaboratorsModal__permissions-header">Read</div>
              <div className="CollaboratorsModal__permissions-subtext">Read-only permissions. Can only pull updates</div>
            </li>

            {
              (sectionType !== 'dataset')
              && (
                <li
                  role="presentation"
                  onClick={() => this._setPermission('readwrite')}
                >
                  <div className="CollaboratorsModal__permissions-header">Write</div>
                  <div className="CollaboratorsModal__permissions-subtext">Read/Write permissions. Can sync to branches other than master</div>
                </li>
              )
            }

            <li
              role="presentation"
              onClick={() => this._setPermission('owner')}
            >
              <div className="CollaboratorsModal__permissions-header">Admin</div>
              <div className="CollaboratorsModal__permissions-subtext">Admin permissions. Can sync to master and manage collaborators</div>
            </li>

          </ul>

        </div>

        <ButtonLoader
          className="ButtonLoader__collaborator Btn__plus Btn--round Btn--medium"
          buttonState={buttonLoaderAddCollaborator}
          buttonText=""
          params={{}}
          buttonDisabled={disableAddButton}
          clicked={this._addCollaborator}
        />
      </div>
    );
  }
}

export default CollaboratorSearch;
