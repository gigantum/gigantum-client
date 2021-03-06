// vendor
import React from 'react';
// assets
import './BrowserSupport.scss';
import gigantumSrc from 'Images/logos/gigantum-client.svg';


const BrowserSupport = () => (
  <div className="BrowserSupport">
    <img
      className="BrowserSupport__img"
      src={gigantumSrc}
      alt="Gigantum"
    />
    <p>Gigantum currently only supports Chrome, Safari and Firefox</p>
    <p>We intend on supporting all major browsers in the near future</p>
  </div>
);

export default BrowserSupport;
