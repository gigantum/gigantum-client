// vendor
import React, { PureComponent } from 'react';
// components
import CustomAppsTable from '../table/CustomAppsTable';
import AddCustomApp from '../add/AddCustomApp';
// assets
import './CustomAppsCard.scss';

type Props = {
  name: string,
  owner: string,
  relay: Object,
  customAppsMutations: Object,
  customApps: Object,
  isLocked: boolean,
}

class CustomAppsCard extends PureComponent<Props> {
  render() {
    const {
      name,
      owner,
      relay,
      customAppsMutations,
      customApps,
      isLocked,
    } = this.props;
    return (
      <div className="CustomApps Card Card--auto Card--no-hover column-1-span-12 relative">
        <AddCustomApp
          customAppsMutations={customAppsMutations}
          relay={relay}
          name={name}
          owner={owner}
          isLocked={isLocked}
        />
        <CustomAppsTable
          customAppsMutations={customAppsMutations}
          customApps={customApps}
          relay={relay}
          name={name}
          owner={owner}
          isLocked={isLocked}
        />
      </div>
    );
  }
}

export default CustomAppsCard;
