plotPoints = function (L, map, points) {
    let layer = new L.featureGroup();
    for (let [idx, latlng] of points.entries()) {
        let marker = this.plotPoint(latlng, null, false, null); // don't plot markers individually, rather as a featureGroup
        layer.addLayer(marker);
    }
}
