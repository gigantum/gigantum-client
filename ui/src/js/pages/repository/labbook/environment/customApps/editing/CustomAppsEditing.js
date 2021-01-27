// @flow
// vendor
import React, { PureComponent } from 'react';
// Assets
import './CustomAppsEditing.scss';

type Props = {
  node: {
    filename: string,
  },
  nodeMissing: boolean,
  setFile: Function,
}

class CustomAppsEditing extends PureComponent<Props> {
  render() {
    const {
      node,
      setFile,
      nodeMissing,
    } = this.props;

    const buttonText = nodeMissing ? 'Upload Missing File' : 'Replace File...';

    return (
      <div className="CustomAppsEditing flex">
        <label
          htmlFor="update_secret"
          className="CustomAppsTable__label"
        >
          {/* <div
            className="Btn Btn--allStyling Btn--noMargin Btn--action padding--horizontal"
          >
            {buttonText}
          </div>
          <input
            id="update_secret"
            className="hidden"
            type="file"
            onChange={evt => setFile(node, evt.target.files[0])}
          /> */}
        </label>
      </div>
    );
  }
}

export default CustomAppsEditing;
