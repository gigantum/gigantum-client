// @flow
// vendor
import React, { Component } from 'react';
import classNames from 'classnames';
// store
import { setErrorMessage } from 'JS/redux/actions/footer';
// assets
import './CustomAppsActions.scss';

type Props = {
  editCustomApp: Function,
  appName: string,
  isEditing: boolean,
  isLocked: boolean,
  name: string,
  nodeMissing: boolean,
  owner: string,
  customAppsMutations: {
    removeCustomApp: Function,
  },
}

class CustomAppsAction extends Component<Props> {
  state = {
    popupVisible: false,
  }

  /**
  *  @param {}
  *  triggers delete customApp mutation
  *  @return {}
  */
  _removeCustomApp = () => {
    const {
      appName,
      name,
      owner,
      customAppsMutations,
    } = this.props;
    const data = {
      appName,
    };

    const deleteCallback = (response, error) => {
      if (error) {
        setErrorMessage(owner, name, 'An error occured while attempting to delete custom app', error);
      }
    };

    customAppsMutations.removeCustomApp(data, deleteCallback);
  }

  /**
  *  @param {Obect} evt
  *  @param {boolean} popupVisible - boolean value for hiding and showing popup state
  *  triggers favoirte unfavorite mutation
  *  @return {}
  */
  _togglePopup(evt, popupVisible) {
    if (!popupVisible) {
      /**
       * only stop propagation when closing popup,
       * other menus won't close on click if propagation is stopped
       */
      evt.stopPropagation();
    }
    this.setState({ popupVisible });
  }

  render() {
    const {
      editCustomApp,
      appName,
      isEditing,
      isLocked,
      nodeMissing,
    } = this.props;
    const { popupVisible } = this.state;
    const popupCSS = classNames({
      CustomAppsActions__popup: true,
      hidden: !popupVisible || isEditing,
      Tooltip__message: true,
    });
    const lockDelete = isEditing || isLocked;
    return (
      <div className="CustomAppsAction flex justify--space-around align-items--end">
        <div className="relative">
          <button
            className="Btn Btn--medium Btn--noMargin Btn--round Btn__delete-secondary Btn__delete-secondary--medium"
            type="button"
            onClick={(evt) => { this._togglePopup(evt, true); }}
            disabled={lockDelete}
          />
          <div className={popupCSS}>
            <div className="Tooltip__pointer" />
            <p className="margin-top--0">Are you sure?</p>
            <div className="flex justify--space-around">
              <button
                className="CustomApps__btn--round CustomApps__btn--cancel"
                onClick={(evt) => { this._togglePopup(evt, false); }}
                type="button"
              />
              <button
                className="CustomApps__btn--round CustomApps__btn--add"
                onClick={this._removeCustomApp}
                type="button"
              />
            </div>
          </div>
        </div>
        {
          !nodeMissing
          && (
          <button
            className="Btn Btn--medium Btn--noMargin Btn--round Btn__edit-secondary Btn__edit-secondary--medium"
            type="button"
            disabled={isLocked}
            onClick={() => editCustomApp(appName)}
          />
          )
        }
      </div>
    );
  }
}

export default CustomAppsAction;
