// vendor
import React, { Component } from 'react';
// assets
import './AddCustomApp.scss';
// utils

type Props = {
  customAppsMutations: Object,
  isLocked: boolean,
}

export default class AddCustomApp extends Component<Props> {
  state = {
    description: '',
    name: '',
    port: '',
    command: '',
  }

  /**
  *  @param {}
  *  calls insert and upload file mutations
  *  @calls {props.secretsMutations.uploadCustomApp}
  */
  _addCustomApp() {
    const {
      name,
      description,
      port,
      command,
    } = this.state;
    console.log(this.props);
    const { customAppsMutations } = this.props;
    const insertData = {
      appName: name,
      description,
      port,
      command,
    };

    const callback = (response, error) => {
      if (response) {
        this._cancel();
      }
      if (error) {
        this.setState({ error: error[0].message });
      }
    };

    customAppsMutations.insertCustomApp(insertData, callback);
  }

  /**
  *  @param {evt} Object
  * updates field
  */
  _updateField(field, evt) {
    this.setState({ [field]: evt.target.value });
  }

  _cancel() {
    this.setState({
      description: '',
      name: '',
      port: '',
      command: '',
    });
  }

  render() {
    const {
      description,
      name,
      port,
      command,
      showError,
      error,
    } = this.state;
    const { isLocked } = this.props;
    const allowSave = description && name && port;
    const allowCancel = description || name || port || command;
    return (
      <div className="AddCustomApp">
        <div className="AddCustomApp__form flex justify--space-between">
          <div className="AddCustomApp__field flex-1 flex flex--column justify--flex-start">
            <h6 className="AddCustomApps__h6 relative">
              <b>Name</b>
            </h6>
            <input
              className="AddCustomApp__input"
              type="text"
              value={name}
              onChange={evt => this._updateField('name', evt)}
            />
          </div>
          <div className="AddCustomApp__field flex flex-2 flex--column justify--flex-start">
            <h6 className="AddCustomApps__h6 relative">
              <b>Description</b>
            </h6>
            <input
              className="AddCustomApp__input"
              type="text"
              value={description}
              onChange={evt => this._updateField('description', evt)}
            />
          </div>
          <div className="AddCustomApp__field flex flex-1 flex--column justify--flex-start">
            <h6 className="AddCustomApps__h6 relative">
              <b>Port</b>
            </h6>
            <input
              className="AddCustomApp__input"
              type="text"
              value={port}
              onChange={evt => this._updateField('port', evt)}
            />
          </div>
          <div className="flex-1 AddCustomApp__field flex flex-3 flex--column justify--flex-start">
            <h6 className="AddCustomApps__h6 relative">
              <b>Command</b>
            </h6>
            <input
              className="AddCustomApp__input"
              type="text"
              value={command}
              placeholder="Optional command to run when launching"
              onChange={evt => this._updateField('command', evt)}
            />
          </div>
        </div>
        <div className="AddCustomApp__actions flex justify--right">
          { error
            && <p className="AddCustomApps__paragraph AddCustomApps__paragraph--error error">{error}</p>}
          <button
            type="button"
            className="Btn Btn--flat AddCustomApps__btn"
            disabled={!allowCancel}
            onClick={() => this._cancel()}
          >
            Cancel
          </button>
          <button
            disabled={!allowSave || showError || isLocked}
            type="button"
            className="Btn Btn--last"
            onClick={() => this._addCustomApp()}
          >
            Add
          </button>
        </div>
      </div>
    );
  }
}
