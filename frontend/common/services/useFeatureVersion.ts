import { FeatureState, FeatureVersion, Res } from 'common/types/responses'
import { Req } from 'common/types/requests'
import { service } from 'common/service'
import { getStore } from 'common/store'
import {
  createVersionFeatureState,
  getVersionFeatureState,
  updateVersionFeatureState,
} from './useVersionFeatureState'
import { deleteFeatureSegment } from './useFeatureSegment'
import transformCorePaging from 'common/transformCorePaging'
import Utils from 'common/utils/utils'
import { updateSegmentPriorities } from './useSegmentPriority'

export const featureVersionService = service
  .enhanceEndpoints({ addTagTypes: ['FeatureVersion'] })
  .injectEndpoints({
    endpoints: (builder) => ({
      createAndSetFeatureVersion: builder.mutation<
        Res['featureVersion'],
        Req['createAndSetFeatureVersion']
      >({
        invalidatesTags: [{ id: 'LIST', type: 'FeatureVersion' }],
        queryFn: async (query: Req['createAndSetFeatureVersion']) => {
          const featureStatesToCreate: Req['createFeatureVersion']['feature_states_to_create'] =
            query.featureStates.filter((v) => !v.id)
          const featureStatesToUpdate: Req['createFeatureVersion']['feature_states_to_update'] =
            query.featureStates.filter((v) => !v.id)
          const segmentIdsToDeleteOverrides: Req['createFeatureVersion']['segment_ids_to_delete_overrides'] =
            []

          // Step 1: Create a new feature version
          const versionRes: { data: FeatureVersion } =
            await createFeatureVersion(getStore(), {
              environmentId: query.environmentId,
              featureId: query.featureId,
              feature_states_to_create: featureStatesToCreate,
              feature_states_to_update: featureStatesToUpdate,
              publish_immediately: !query.skipPublish,
              segment_ids_to_delete_overrides: segmentIdsToDeleteOverrides,
            })

          const currentFeatureStates: { data: FeatureState[] } =
            await getVersionFeatureState(getStore(), {
              environmentId: query.environmentId,
              featureId: query.featureId,
              sha: versionRes.data.uuid,
            })

          const res = currentFeatureStates.data

          //Step 2: Update feature segment priorities before saving feature states
          const prioritiesToUpdate = query.featureStates
            .filter((v) => !v.toRemove && !!v.feature_segment)
            .map((v) => {
              const matchingFeatureSegment = res?.find(
                (currentFeatureState) =>
                  v.feature_segment?.segment ===
                  currentFeatureState.data.feature_segment?.segment,
              )
              return {
                id: matchingFeatureSegment!.data.feature_segment!.id!,
                priority: v.feature_segment!.priority,
              }
            })
          if (prioritiesToUpdate.length) {
            await updateSegmentPriorities(getStore(), prioritiesToUpdate)
          }

          const ret = {
            data: res.map((item) => ({
              ...item,
              version_sha: versionRes.data.uuid,
            })),
            error: res.find((v) => !!v.error)?.error,
          }

          return ret as any
        },
      }),
      createFeatureVersion: builder.mutation<
        Res['featureVersion'],
        Req['createFeatureVersion']
      >({
        invalidatesTags: [{ id: 'LIST', type: 'FeatureVersion' }],
        query: ({
          environmentId,
          featureId,
          ...rest
        }: Req['createFeatureVersion']) => ({
          body: { ...rest },
          method: 'POST',
          url: `environments/${environmentId}/features/${featureId}/versions/`,
        }),
      }),
      getFeatureVersion: builder.query<
        Res['featureVersion'],
        Req['getFeatureVersion']
      >({
        providesTags: (res) => [{ id: res?.uuid, type: 'FeatureVersion' }],
        query: (query: Req['getFeatureVersion']) => ({
          url: `environments/${query.environmentId}/features/${query.featureId}/versions/${query.uuid}`,
        }),
      }),
      getFeatureVersions: builder.query<
        Res['featureVersions'],
        Req['getFeatureVersions']
      >({
        providesTags: [{ id: 'LIST', type: 'FeatureVersion' }],
        query: (query) => ({
          url: `environments/${query.environmentId}/features/${
            query.featureId
          }/versions/?${Utils.toParam(query)}`,
        }),
        transformResponse: (
          baseQueryReturnValue: Res['featureVersions'],
          meta,
          req,
        ) => {
          return transformCorePaging(req, baseQueryReturnValue)
        },
      }),
      publishFeatureVersion: builder.mutation<
        Res['featureVersion'],
        Req['publishFeatureVersion']
      >({
        invalidatesTags: [{ id: 'LIST', type: 'FeatureVersion' }],
        query: (query: Req['publishFeatureVersion']) => ({
          body: query,
          method: 'POST',
          url: `environments/${query.environmentId}/features/${query.featureId}/versions/${query.sha}/publish/`,
        }),
      }),
      // END OF ENDPOINTS
    }),
  })

export async function createFeatureVersion(
  store: any,
  data: Req['createFeatureVersion'],
  options?: Parameters<
    typeof featureVersionService.endpoints.createFeatureVersion.initiate
  >[1],
) {
  return store.dispatch(
    featureVersionService.endpoints.createFeatureVersion.initiate(
      data,
      options,
    ),
  )
}
export async function publishFeatureVersion(
  store: any,
  data: Req['publishFeatureVersion'],
  options?: Parameters<
    typeof featureVersionService.endpoints.publishFeatureVersion.initiate
  >[1],
) {
  return store.dispatch(
    featureVersionService.endpoints.publishFeatureVersion.initiate(
      data,
      options,
    ),
  )
}
export async function createAndSetFeatureVersion(
  store: any,
  data: Req['createAndSetFeatureVersion'],
  options?: Parameters<
    typeof featureVersionService.endpoints.createAndSetFeatureVersion.initiate
  >[1],
) {
  return store.dispatch(
    featureVersionService.endpoints.createAndSetFeatureVersion.initiate(
      data,
      options,
    ),
  )
}
export async function getFeatureVersions(
  store: any,
  data: Req['getFeatureVersions'],
  options?: Parameters<
    typeof featureVersionService.endpoints.getFeatureVersions.initiate
  >[1],
) {
  return store.dispatch(
    featureVersionService.endpoints.getFeatureVersions.initiate(data, options),
  )
}
export async function getFeatureVersion(
  store: any,
  data: Req['getFeatureVersion'],
  options?: Parameters<
    typeof featureVersionService.endpoints.getFeatureVersion.initiate
  >[1],
) {
  return store.dispatch(
    featureVersionService.endpoints.getFeatureVersion.initiate(data, options),
  )
}
// END OF FUNCTION_EXPORTS

export const {
  useCreateAndSetFeatureVersionMutation,
  useCreateFeatureVersionMutation,
  useGetFeatureVersionQuery,
  useGetFeatureVersionsQuery,
  // END OF EXPORTS
} = featureVersionService

/* Usage examples:
const { data, isLoading } = useGetFeatureVersionQuery({ id: 2 }, {}) //get hook
const [createFeatureVersion, { isLoading, data, isSuccess }] = useCreateFeatureVersionMutation() //create hook
featureVersionService.endpoints.getFeatureVersion.select({id: 2})(store.getState()) //access data from any function
*/
