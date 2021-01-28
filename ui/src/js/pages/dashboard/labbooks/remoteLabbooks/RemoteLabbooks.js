// @flow
// vendor
import React, { Component } from 'react';
import {
  createPaginationContainer,
  graphql,
} from 'react-relay';
// components
import RemoteLabbookPanel from 'Pages/dashboard/labbooks/remoteLabbooks/RemoteLabbookPanel';
import DeleteLabbook from 'Pages/repository/shared/modals/DeleteLabbook';
import CardLoader from 'Pages/dashboard/shared/loaders/CardLoader';
import NoResults from 'Pages/dashboard/shared/NoResults';
import LoginPrompt from 'Pages/repository/shared/modals/LoginPrompt';
// queries
import UserIdentity from 'JS/Auth/UserIdentity';
// store
import store from 'JS/redux/store';
// assets
import './RemoteLabbooks.scss';


type Props = {
  filterLabbooks: Function,
  filterState: string,
  forceLocalView: Function,
  relay: {
    isLoading: Function,
    loadMore: Function,
  },
  remoteLabbooks: {
    remoteLabbooks: {
      edges: Array<Object>,
      pageInfo: {
        hasNextPage: boolean,
      }
    }
  },
  remoteLabbooksId: string,
  setFilterValue: Function,
};

class RemoteLabbooks extends Component<Props> {
  state = {
    deleteData: {
      remoteId: null,
      remoteOwner: null,
      remoteLabbookName: null,
      remoteUrl: null,
      existsLocally: null,
    },
    deleteModalVisible: false,
    showLoginPrompt: false,
  };

  /*
    loads more remote labbooks on mount
  */
  componentDidMount() {
    const { forceLocalView, remoteLabbooks } = this.props;
    if (
      remoteLabbooks.remoteLabbooks
      && remoteLabbooks.remoteLabbooks.pageInfo.hasNextPage
    ) {
      this._loadMore();
    }

    UserIdentity.getUserIdentity().then((response) => {
      if (navigator.onLine) {
        if (response.data) {
          if (!response.data.userIdentity.isSessionValid) {
            forceLocalView();
          }
        }
      } else {
        forceLocalView();
      }
    });
  }

  /**
    *  @param {}
    *  loads more labbooks using the relay pagination container
  */
  _loadMore = () => {
    const {
      forceLocalView,
      relay,
      remoteLabbooks,
    } = this.props;

    if (relay.isLoading()) {
      return;
    }

    UserIdentity.getUserIdentity().then((response) => {
      if (navigator.onLine) {
        if (response.data) {
          if (response.data.userIdentity.isSessionValid) {
            if (remoteLabbooks.remoteLabbooks.pageInfo.hasNextPage) {
              relay.loadMore(
                8, // Fetch the next 8 items
                () => {
                  const newProps = this.props;
                  if (
                    newProps.remoteLabbooks.remoteLabbooks
                    && newProps.remoteLabbooks.remoteLabbooks.pageInfo.hasNextPage
                  ) {
                    this._loadMore();
                  }
                },
              );
            }
          } else {
            forceLocalView();
          }
        }
      } else {
        forceLocalView();
      }
    });
  }

  /**
   *  @param {} -
   *  hides login prompt
  */
  _closeLoginPromptModal = () => {
    this.setState({ showLoginPrompt: false });
  }

  /**
    *  @param {object} deleteData
    *  changes the delete modal's visibility and changes the data passed to it
  */
  _toggleDeleteModal = (deleteData) => {
    if (deleteData) {
      this.setState({
        deleteData,
        deleteModalVisible: true,
      });
    } else {
      this.setState({
        deleteData: {
          remoteId: null,
          remoteOwner: null,
          remoteUrl: null,
          remoteLabbookName: null,
          existsLocally: null,
        },
        deleteModalVisible: false,
      });
    }
  }

  render() {
    const {
      filterLabbooks,
      filterState,
      remoteLabbooks,
      remoteLabbooksId,
      relay,
      setFilterValue,
    } = this.props;
    const {
      deleteData,
      deleteModalVisible,
      showLoginPrompt,
    } = this.state;
    const { hasNextPage } = remoteLabbooks.remoteLabbooks.pageInfo;

    if (
      remoteLabbooks
      && (remoteLabbooks.remoteLabbooks !== null)
    ) {
      const labbooks = filterLabbooks(
        remoteLabbooks.remoteLabbooks.edges,
        filterState,
      );

      return (
        <div className="Labbooks__listing">
          <div className="grid">
            {
            labbooks.length
              ? labbooks.map(edge => (
                <RemoteLabbookPanel
                  {...this.props}
                  toggleDeleteModal={this._toggleDeleteModal}
                  labbookListId={remoteLabbooksId}
                  key={edge.node.owner + edge.node.name}
                  ref={`RemoteLabbookPanel${edge.node.name}`}
                  edge={edge}
                  existsLocally={edge.node.isLocal}
                />
              ))
              : !relay.isLoading()
            && store.getState().labbookListing.filterText
            && <NoResults setFilterValue={setFilterValue} />
            }
            { Array(5).fill(1).map((value, index) => (
              <CardLoader
                key={`RemoteLabbooks_paginationLoader${index}`}
                index={index}
                isLoadingMore={hasNextPage}
              />
            ))}

          </div>

          { deleteModalVisible
            && (
              <DeleteLabbook
                {...deleteData}
                {...this.props}
                owner={deleteData.remoteOwner}
                name={deleteData.remoteLabbookName}
                handleClose={() => { this._toggleDeleteModal(); }}
                remoteConnection="RemoteLabbooks_remoteLabbooks"
                toggleModal={this._toggleDeleteModal}
                remoteDelete
              />
            )}

          <LoginPrompt
            showLoginPrompt={showLoginPrompt}
            closeModal={this._closeLoginPromptModal}
          />
        </div>
      );
    }

    return (<div />);
  }
}

export default createPaginationContainer(
  RemoteLabbooks,
  {
    remoteLabbooks: graphql`
      fragment RemoteLabbooks_remoteLabbooks on LabbookList{
        remoteLabbooks(first: $first, after: $cursor, orderBy: $orderBy, sort: $sort)@connection(key: "RemoteLabbooks_remoteLabbooks", filters: []){
          edges {
            node {
              name
              description
              visibility
              owner
              id
              isLocal
              creationDateUtc
              modifiedDateUtc
              importUrl
            }
            cursor
          }
          pageInfo {
            endCursor
            hasNextPage
            hasPreviousPage
            startCursor
          }
        }
      }
    `,
  },
  {
    direction: 'forward',
    getConnectionFromProps(props) {
      return props.remoteLabbooks.remoteLabbooks;
    },
    getFragmentVariables(prevVars, first) {
      return {
        ...prevVars,
        first,
      };
    },
    getVariables(props, {
      first, cursor, orderBy, sort,
    }, fragmentVariables) {
      first = 10;
      cursor = props.remoteLabbooks.remoteLabbooks.pageInfo.endCursor;
      orderBy = fragmentVariables.orderBy;
      sort = fragmentVariables.sort;
      return {
        first,
        cursor,
        orderBy,
        sort,
        // in most cases, for variables other than connection filters like
        // `first`, `after`, etc. you may want to use the previous values.
      };
    },
    query: graphql`
      query RemoteLabbooksPaginationQuery(
        $first: Int!
        $cursor: String
        $orderBy: String
        $sort: String
      ) {
        labbookList{
          ...RemoteLabbooks_remoteLabbooks
        }
      }
    `,
  },
);
