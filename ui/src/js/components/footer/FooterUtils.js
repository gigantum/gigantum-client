// vendor
import JobStatus from 'JS/utils/JobStatus';
import AnsiUp from 'ansi_up';
// store
import {
  setMultiInfoMessage,
  setErrorMessage,
  setUploadMessageUpdate,
  setUploadMessageRemove,
} from 'JS/redux/actions/footer';
// mutations
import FetchLabbookEdgeMutation from 'Mutations/repository/fetch/FetchLabbookEdgeMutation';
import FetchDatasetEdgeMutation from 'Mutations/repository/fetch/FetchDatasetEdgeMutation';
import FetchDatasetFilesMutation from 'Mutations/repository/fetch/FetchDatasetFilesMutation';
import FetchLabbookDatasetFilesMutation from 'Mutations/repository/fetch/FetchLabbookDatasetFilesMutation';
// Queries
import UpdateDasetCommits from 'Pages/repository/shared/header/branches/UpdateDatasetCommits';

const ansiUp = new AnsiUp();

const hideModal = () => {
  document.getElementById('modal__cover').classList.add('hidden');
  document.getElementById('loader').classList.add('hidden');
};

const messageParser = (response) => {
  let fullMessage = (response.data.jobStatus.jobMetadata.indexOf('feedback') > -1) ? JSON.parse(response.data.jobStatus.jobMetadata).feedback : '';
  fullMessage = fullMessage.lastIndexOf('\n') === (fullMessage.length - 1)
    ? fullMessage.slice(0, fullMessage.length - 1)
    : fullMessage;

  const html = ansiUp.ansi_to_html(fullMessage);

  const lastIndex = (fullMessage.lastIndexOf('\n') > -1)
    ? fullMessage.lastIndexOf('\n')
    : 0;

  let message = fullMessage.slice(lastIndex, fullMessage.length);

  if (message.indexOf('[0m') > 0) {
    const res = [];
    let index = 0;

    while (fullMessage.indexOf('\n', index + 1) > 0) {
      index = fullMessage.indexOf('\n', index + 1);
      res.push(index);
    }

    message = fullMessage.slice(res[res.length - 2], res[res.length - 1]);
  }
  return {
    html,
    message,
  };
};

const FooterUtils = {
  /**
   *  @param {number}
   *  iterate value of index within the bounds of the array size
   *  @return {}
   */
  getJobStatus: (owner, name, footerData) => {
    const {
      result,
      type,
      key,
      footerCallback,
      callback,
      successCall,
      failureCall,
      id,
      hideFooter,
    } = footerData;
    /**
      *  @param {}
      *  refetches job status
      *  @return {}
      */
    const refetch = () => {
      setTimeout(() => {
        fetchStatus();
      }, 1000);
    };
    /**
      *  @param {}
      *  fetches job status for background message
      *  updates footer with a message
      *  @return {}
      */
    const fetchStatus = () => {
      const resultType = result[type];
      const resultKey = resultType ? resultType[key] : false;
      const mutations = {
        FetchLabbookEdgeMutation,
        FetchDatasetEdgeMutation,
        FetchDatasetFilesMutation,
        FetchLabbookDatasetFilesMutation,
      };

      if (resultKey) {
        JobStatus.updateFooterStatus(result[type][key]).then((response) => {
          if (response.data
              && response.data.jobStatus
              && response.data.jobStatus.jobMetadata
          ) {
            const responseId = id || response.data.jobStatus.id;
            const { html, message } = messageParser(response);
            // executes while job status is still running, refetches until status is finished or failed
            if ((response.data.jobStatus.status === 'started')
              || (response.data.jobStatus.status === 'queued')) {
              if (html.length) {
                const messageData = {
                  id: responseId,
                  message,
                  isLast: false,
                  error: false,
                  status: response.data.jobStatus.status,
                  messageBody: [{ message: html }],
                  messageListOpen: !hideFooter,
                  buildProgress: type === 'buildImage',
                };
                setMultiInfoMessage(owner, name, messageData);
              }
              refetch();
            // executes when job status has completed
            // TODO handle configure dataset callback
            } else if (response.data.jobStatus.status === 'finished') {
              const messageData = {
                id: responseId,
                message,
                isLast: true,
                error: null,
                status: response.data.jobStatus.status,
                messageBody: [{ message: html }],
                buildProgress: type === 'buildImage',
              };

              setMultiInfoMessage(owner, name, messageData);
              hideModal();

              if (footerCallback && footerCallback.finished) {
                const callbackData = {
                  response,
                  successCall,
                  mutations,
                };
                footerCallback.finished(callbackData);
              } else if (callback) {
                callback(response);
              }
            // executes when job status has failed
            } else if (response.data.jobStatus.status === 'failed') {
              const errorMessage = response.data.jobStatus.failureMessage;
              hideModal();

              const metaData = JSON.parse(response.data.jobStatus.jobMetadata);

              if (footerCallback && footerCallback.failed) {
                const callbackData = {
                  response,
                  failureCall,
                  mutations,
                };
                // footerCallback.failed(callbackData);
                if (failureCall) {
                  failureCall(errorMessage, metaData);
                } else {
                  footerCallback.failed(callbackData);
                }
              } else if (callback) {
                callback(response);
              }

              const messageData = {
                id: responseId,
                message: errorMessage,
                isLast: true,
                status: response.data.jobStatus.status,
                error: true,
                messageListOpen: true,
                messageBody: [{ message: html }],
                buildProgress: type === 'buildImage',
              };
              setMultiInfoMessage(owner, name, messageData);
            } else {
              // refetch status data not ready
              refetch();
            }
          } else {
            // refetch status data not ready
            refetch();
          }
        });
      } else {
        setErrorMessage(
          owner,
          name,
          'There was an error fetching job status.',
          [{ message: 'Callback error from the API', status: 'failed' }],
        );
      }
    };

    // trigger fetch
    fetchStatus();
  },
  /**
    *  @param {object} mutationResponse
    *  @param {function} refetch
    *  fetches job status for background message
    *  updates footer with a message
    *  @return {}
    */
  datasetUploadStatus: (mutationResponse, finishedCallback, variables) => {
    const {
      completeDatasetUploadTransaction,
    } = mutationResponse;
    /**
      *  @param {}
      *  fetches job status for background message
      *  updates footer with a message
      *  @return {}
      */
    const fetchStatus = (owner, name, data) => {
      const {
        backgroundJobKey,
      } = data;

      if (backgroundJobKey) {
        JobStatus.updateFooterStatus(backgroundJobKey).then((response) => {
          const { jobStatus } = response.data;
          const metaData = JSON.parse(jobStatus.jobMetadata);

          if ((jobStatus.status === 'started')
            || (jobStatus.status === 'queued')) {
            setTimeout(() => {
              fetchStatus(owner, name, { backgroundJobKey });

              if (metaData.feedback === undefined) {
                setUploadMessageUpdate(
                  'Please wait while contents are analyzed.',
                  1,
                  0,
                );
              } else {
                setUploadMessageUpdate(
                  metaData.feedback,
                  1,
                  parseFloat(metaData.percent_complete),
                );
              }
            }, 1000);
          } else if ((jobStatus.status === 'finished')
            || (jobStatus.status === 'failed')) {
            finishedCallback();

            setUploadMessageUpdate(
              metaData.feedback,
              1,
              parseFloat(metaData.percent_complete),
            );

            UpdateDasetCommits.getDatasetCommits(variables);

            setTimeout(() => {
              setUploadMessageRemove(metaData.feedback);
            }, 2000);
          }
        });
      }
    };

    const data = { backgroundJobKey: completeDatasetUploadTransaction.backgroundJobKey };
    const { name, owner } = variables;
    // trigger fetch
    fetchStatus(name, owner, data);
  },
};

export default FooterUtils;
