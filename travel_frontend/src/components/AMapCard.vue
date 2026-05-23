<template>
  <div class="amap-card-wrapper">
    <div class="amap-container" :id="mapId"></div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, onUnmounted } from 'vue'
import AMapLoader from '@amap/amap-jsapi-loader'
import { v4 as uuidv4 } from 'uuid'

const props = defineProps<{
  mapData: {
    type: string
    pois?: Array<{ name: string, location: string }>
    routes?: Array<{ path: string[] }>
  }
}>()

const mapId = ref(`map-${uuidv4()}`)
let mapInstance: any = null

onMounted(() => {
  initMap()
})

onUnmounted(() => {
  if (mapInstance) {
    mapInstance.destroy()
  }
})

const initMap = async () => {
  // 设置安全密钥 (如果有的话可以填入，高德 API 2.0 推荐设置)
  // window._AMapSecurityConfig = {
  //   securityJsCode: '你的安全密钥',
  // }

  try {
    const AMap = await AMapLoader.load({
      key: '93bb2fb496265e8fbd1a9e53307bd2a5', // 用户提供的高德 Key
      version: '2.0',
      plugins: ['AMap.Marker', 'AMap.Polyline', 'AMap.Icon']
    })

    // 初始化地图
    mapInstance = new AMap.Map(mapId.value, {
      zoom: 11,
      center: [116.397428, 39.90923], // 默认北京天安门
      mapStyle: 'amap://styles/normal' // 可以换成马卡龙等更柔和的样式
    })

    const { pois, routes } = props.mapData

    let markers: any[] = []
    let polylines: any[] = []

    // 绘制 POI
    if (pois && pois.length > 0) {
      pois.forEach(poi => {
        const [lng, lat] = poi.location.split(',').map(Number)
        const marker = new AMap.Marker({
          position: new AMap.LngLat(lng, lat),
          title: poi.name
        })
        mapInstance.add(marker)
        markers.push(marker)
      })
    }

    // 绘制路线
    if (routes && routes.length > 0) {
      routes.forEach(route => {
        const path = route.path.map(p => {
          const [lng, lat] = p.split(',').map(Number)
          return new AMap.LngLat(lng, lat)
        })

        const polyline = new AMap.Polyline({
          path: path,
          isOutline: true,
          outlineColor: '#ffeeff',
          borderWeight: 2,
          strokeColor: '#3366FF',
          strokeOpacity: 0.8,
          strokeWeight: 6,
          strokeStyle: 'solid',
          lineJoin: 'round',
          lineCap: 'round',
          zIndex: 50
        })
        mapInstance.add(polyline)
        polylines.push(polyline)
      })
    }

    // 自动调整视野
    const overlays = [...markers, ...polylines]
    if (overlays.length > 0) {
      // 延迟一下等待渲染
      setTimeout(() => {
        mapInstance.setFitView(overlays)
      }, 300)
    }

  } catch (e) {
    console.error('高德地图加载失败', e)
  }
}
</script>

<style scoped lang="scss">
.amap-card-wrapper {
  width: 100%;
  margin-top: 12px;
  border-radius: 16px;
  overflow: hidden;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
  border: 1px solid #f0f0f0;
}

.amap-container {
  width: 100%;
  height: 250px; /* 固定高度，避免撑破聊天气泡 */
}
</style>
