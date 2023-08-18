// import propTypes from 'prop-types';
import React, { Component } from 'react'
import data from 'common/data/base/_data'
import ErrorMessage from './ErrorMessage'
import SuccessMessage from './SuccessMessage'
import PlayIcon from './svg/PlayIcon'

export default class TheComponent extends Component {
  static displayName = 'TestWebhook'

  static propTypes = {}

  constructor(props) {
    super(props)
    this.state = {}
  }

  submit = () => {
    this.setState({ error: false, loading: true, success: false })
    data
      .post(this.props.webhook, JSON.parse(this.props.json))
      .then(() => {
        this.setState({ loading: false, success: true })
      })
      .catch((e) => {
        if (e.text) {
          e.text().then((error) =>
            this.setState({
              error: `The server returned an error: ${error}`,
              loading: false,
            }),
          )
        } else {
          this.setState({
            error: 'There was an error posting to your webhook.',
            loading: false,
          })
        }
      })
  }

  render() {
    const {
      state: { error, loading, success },
      submit,
    } = this
    return (
      <div>
        {error && <ErrorMessage error={this.state.error} />}
        {success && (
          <SuccessMessage message='Your API returned with a successful 200 response.' />
        )}
        <Button
          type='button'
          id='try-it-btn'
          disabled={loading || !this.props.webhook}
          onClick={submit}
          className='btn btn--with-icon primary'
        >
          Test your webhook{' '}
          <PlayIcon className='btn__icon btn__icon--small' alt='Run' />
        </Button>
      </div>
    )
  }
}