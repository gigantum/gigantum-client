// @flow
// vendor
import React, { Component } from 'react';
import classNames from 'classnames';
// components
import CustomAppsAction from '../actions/CustomAppsActions';
import CustomAppsEditing from '../editing/CustomAppsEditing';
// assets
import './CustomAppsTable.scss';

type Props = {
  isLocked: boolean,
  customApps: {
    edges: Array<Object>,
  },
  customAppsMutations: {
    deleteCustomApp: Function,
    uploadCustomApp: Function,
  },
}

class CustomAppsTable extends Component<Props> {
  state = {
    tooltipVisible: false,
    editedCustomApps: new Set(),
    addedFiles: new Map(),
  }

  /**
    * @param {String} filename
    * sets tooltipVisible in state
    *
    * @return {}
  */
  _setTooltipVisible = (filename) => {
    this.setState((state) => {
      const tooltipVisible = (state.tooltipVisible === filename) ? null : filename;
      return { tooltipVisible };
    });
  }

  /**
    * @param {String} filename
    * sets editedCustomApps in state
    *
    * @return {}
  */
  _editCustomApp = (filename) => {
    const { addedFiles, editedCustomApps } = this.state;
    const newEditedCustomApps = new Set(editedCustomApps);
    const newAddedFiles = new Map(addedFiles);

    if (newEditedCustomApps.has(filename)) {
      newEditedCustomApps.delete(filename);
      newAddedFiles.delete(filename);
    } else {
      newEditedCustomApps.add(filename);
    }
    this.setState({ addedFiles: newAddedFiles, editedCustomApps: newEditedCustomApps });
  }

  /**
  *  @param {String} filename
  *  @param {Object} file
  *  @param {Number} id
  *  @param {Boolean} isPresent
  * sets file in state
  */
  _setApp = (node, file) => {
    const { filename, id, isPresent } = node;
    const { addedFiles } = this.state;
    const newAddedFiles = new Map(addedFiles);
    newAddedFiles.set(filename, file);
    this.setState({ addedFiles: newAddedFiles }, () => {
      this._replaceApp(filename, id, isPresent);
    });
  }

  /**
  *  @param {String} filename
  *  @param {String} path
  *  calls insert and upload file mutations
  *  @calls {props.customAppsMutations.uploadCustomApp}
  *  @calls {props.customAppsMutations.deleteCustomApp}
  */
  _replaceApp = (filename, id, isPresent) => {
    const { addedFiles } = this.state;
    const { customAppsMutations } = this.props;

    let file = addedFiles.get(filename);
    file = new File([file], filename, { type: file.type });
    const uploadData = {
      file,
      filename,
      component: this,
      id,
    };

    const data = {
      filename,
      id,
    };
    if (isPresent) {
      const removeCallback = () => {
        customAppsMutations.uploadCustomApp(uploadData);
      };
      customAppsMutations.deleteCustomApp(data, removeCallback);
      this._editCustomApp(filename);
    } else {
      customAppsMutations.uploadCustomApp(uploadData);
    }
  }

  render() {
    const { addedFiles, editedCustomApps } = this.state;
    const { customApps, isLocked } = this.props;
    console.log(customApps);
    const customAppsArray = customApps || [];
    console.log(customAppsArray);

    return (
      <div className="Table Table--padded">
        <div className="Table__Header Table__Header--medium flex align-items--center">
          <div className="CustomAppsTable__header-file flex-1">Name</div>
          <div className="CustomAppsTable__header-path flex-1">Description</div>
          <div className="CustomAppsTable__header-file flex-1">Port</div>
          <div className="CustomAppsTable__header-path flex-1">Command</div>
          <div className="CustomAppsTable__header-actions">Actions</div>
        </div>
        <div className="Table__Body">
          {
            customAppsArray.map((app) => {
              const isEditing = editedCustomApps.has(app.appName);
              const showEditApp = (isEditing && !isLocked);
              const nameCSS = classNames({
                'CustomAppsTable__row-file flex-1 break-word': true,
                'CustomAppsTable__row-file--editing': isEditing,
              });
              return (
                <div
                  className="Table__Row Table__Row--customApps flex align-items--center"
                  key={app.id}
                >
                  <div className={nameCSS}>
                    <div className="flex">
                      <div className="CustomAppsTable__name">
                        {app.appName}
                      </div>
                    </div>
                    {
                      showEditApp
                      && (
                        <CustomAppsEditing
                          app={app}
                          addedFiles={addedFiles}
                          setApp={this._setApp}
                          replaceApp={this._replaceApp}
                          editCustomApp={this._editCustomApp}
                        />
                      )
                    }
                  </div>
                  <div className="CustomAppsTable__row-path flex-1 break-word">
                    {app.description}
                  </div>
                  <div className="CustomAppsTable__row-path flex-1 break-word">
                    {app.port}
                  </div>
                  <div className="CustomAppsTable__row-path flex-1 break-word">
                    {app.command}
                  </div>
                  <div className="CustomAppsTable__row-actions">
                    <CustomAppsAction
                      {...app}
                      {...this.props}
                      editCustomApp={this._editCustomApp}
                      isEditing={isEditing}
                    />
                  </div>
                </div>
              );
            })

          }
          { (customAppsArray.length === 0)
            && <p className="text-center">No Custom Apps have been added to this project</p>}
        </div>
      </div>
    );
  }
}

export default CustomAppsTable;
