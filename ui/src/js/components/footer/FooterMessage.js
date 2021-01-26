// @flow
import React, { PureComponent } from 'react';
import classNames from 'classnames';
import Moment from 'moment';
// components
import BuildModal from 'Pages/repository/shared/modals/BuildModal';
import OutputMessage from './output/OutputMessage';
// assets
import './FooterMessage.scss';

type Props = {
  messageItem: Object,
  selectedBuildId: string,
  setBuildId: Function,
  updateOpenCount: Function,
  owner: string,
  name: string,
};


class FooterMessage extends PureComponent<Props> {
  state = {
    messageBodyVisible: false,
  }

  /**
  *  @param {} -
  *  sets state to expand body of extra message content
  */
  _showMessageBody = () => {
    const { props } = this;
    this.setState((state) => {
      const messageBodyVisible = !state.messageBodyVisible;
      props.updateOpenCount(messageBodyVisible);

      return { messageBodyVisible };
    });
  }

  render() {
    const {
      owner,
      name,
      messageItem,
      selectedBuildId,
      setBuildId,
    } = this.props;
    const { messageBodyVisible } = this.state;
    const time = `${Moment(messageItem.date).fromNow()}:`;

    // declare css here
    const messageBodyClasses = classNames({
      FooterMessage__body: true,
      hidden: !messageBodyVisible || messageItem.buildProgress,
    });
    const toggleButton = classNames({
      'Btn Btn__toggle': true,
      'Btn__toggle--open': messageBodyVisible,
      hidden: messageItem.buildProgress,
    });
    const bodyCSS = classNames({
      FooterMessage: true,
      'height-auto': messageBodyVisible,
      [messageItem.className]: true,
    });
    const messageTitleCSS = classNames({
      FooterMessage__title: true,
      'FooterMessage__title--collapsed': !messageBodyVisible,
    });

    return (
      <li className={bodyCSS}>
        <div className="FooterMessage__flex">
          <div className="FooterMessage__icon" />

          <div className="FooterMessage__time">
            {time}
          </div>
          <div className="FooterMessage__item">
            <p className={messageTitleCSS}>
              {messageItem.message}
            </p>
          </div>

          { (messageItem.messageBody.length > 0)
            && (
            <div className="FooterMessage__btn FooterMessage__btn--expand">
              <button
                type="button"
                className={toggleButton}
                onClick={() => { this._showMessageBody(); }}
              />
            </div>
            )}
          {
            messageItem.buildProgress
            && (
              <button
                className="Btn Btn--inverted Btn--inverted--white no-wrap align-self--center"
                onClick={() => setBuildId(messageItem.id)}
                type="button"
              >
                View Build Output
              </button>
            )
          }
        </div>
        <div className={messageBodyClasses}>

          <ul>
            {
              messageItem && messageItem.messageBody && messageItem.messageBody.map(item => (
                <li key={messageItem.id}>
                  <OutputMessage item={item} />
                </li>
              ))
            }
          </ul>
        </div>

        {
          (selectedBuildId === messageItem.id)
          && (
            <BuildModal
              setBuildId={setBuildId}
              buildId={selectedBuildId}
              keepOpen
              owner={owner}
              name={name}
            />
          )
        }

      </li>
    );
  }
}

export default FooterMessage;
