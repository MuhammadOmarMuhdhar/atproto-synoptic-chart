// Global variables
let densityData = [];
let postsData = [];
let postsWithCoords = [];
let topicClusters = [];
let svg, g, xScale, yScale, zoom;
let dotsGroup, clustersGroup;
let dataByTime = new Map();
let timeSlices = [];
let currentTimeIndex = 0;
let isPlaying = false;
let playInterval;

// Tooltip
const tooltip = d3.select(".tooltip");

// Time controls
const playButton = d3.select("#play-button");
const slider = d3.select("#time-slider");
const sliderHandle = d3.select("#slider-handle");
const timeDisplay = d3.select("#time-display");

// Zoom controls
const zoomInButton = d3.select("#zoom-in");
const zoomOutButton = d3.select("#zoom-out");

// Color scale
const colorScale = d3.scaleSequential(d3.interpolateBlues).domain([0, 1]);

// Load data and initialize visualization
Promise.all([
    d3.json("../data/density_data.json"),
    d3.json("../data/posts.json"),
    d3.json("../data/topic_clusters.json")
]).then(([density, posts, clusters]) => {
    densityData = density;
    postsData = posts;
    topicClusters = clusters;
    
    // Filter posts that have coordinates
    postsWithCoords = postsData.filter(post => 
        post.UMAP1 !== null && post.UMAP1 !== undefined && 
        post.UMAP2 !== null && post.UMAP2 !== undefined &&
        !isNaN(post.UMAP1) && !isNaN(post.UMAP2)
    );
    
    console.log(`Loaded ${densityData.length} density points and ${postsWithCoords.length} posts with coordinates`);
    
    // Group density data by time
    dataByTime = d3.group(densityData, d => d.calculated_at);
    timeSlices = Array.from(dataByTime.keys()).sort();
    
    console.log(`Found ${timeSlices.length} time slices`);
    
    initializeVisualization();
    setupTimeControls();
    renderTopicClusters();
    updateVisualization();
    
    // Handle window resize
    window.addEventListener('resize', function() {
        const width = window.innerWidth;
        const height = window.innerHeight;
        
        svg.attr("width", width).attr("height", height);
        
        // Reinitialize with new dimensions
        initializeVisualization();
        updateVisualization();
    });
}).catch(error => {
    console.error("Error loading data:", error);
});

function initializeVisualization() {
    const container = d3.select("#chart-container");
    const width = window.innerWidth;
    const height = window.innerHeight;
    
    // Create SVG
    svg = d3.select("#chart")
        .attr("width", width)
        .attr("height", height);
    
    // Create zoom behavior
    zoom = d3.zoom()
        .scaleExtent([0.5, 10])
        .on("zoom", handleZoom);
    
    svg.call(zoom);
    
    // Create main group for zoomable content
    g = svg.append("g");
    
    // Set up scales
    const allX = densityData.map(d => d.x).concat(postsWithCoords.map(d => d.UMAP1));
    const allY = densityData.map(d => d.y).concat(postsWithCoords.map(d => d.UMAP2));
    
    const margin = { top: 50, right: 50, bottom: 100, left: 100 };
    const plotSize = Math.min(width - margin.left - margin.right, height - margin.top - margin.bottom) * 0.8;
    const chartWidth = width - margin.left - margin.right;
    const chartHeight = height - margin.top - margin.bottom;
    
    xScale = d3.scaleLinear()
        .domain(d3.extent(allX))
        .range([margin.left, margin.left + chartWidth]);
    
    yScale = d3.scaleLinear()
        .domain(d3.extent(allY))
        .range([margin.top + chartHeight, margin.top]);
    
    
    // Create group for contours (clipped)
    const defs = svg.append("defs");
    const clipPath = defs.append("clipPath")
        .attr("id", "chart-clip");
    
    clipPath.append("rect")
        .attr("x", margin.left)
        .attr("y", margin.top)
        .attr("width", chartWidth)
        .attr("height", chartHeight);
    
    // Add background rings centered on chart area (zoomable)
    const chartCenterX = margin.left + chartWidth / 2;
    const chartCenterY = margin.top + chartHeight / 2;
    const chartMaxRadius = Math.max(chartWidth, chartHeight);
    
    const ringsGroup = g.append("g").attr("class", "background-rings");
    for (let i = 1; i <= 8; i++) {
        ringsGroup.append("circle")
            .attr("cx", chartCenterX)
            .attr("cy", chartCenterY)
            .attr("r", (chartMaxRadius / 8) * i)
            .attr("fill", "none")
            .attr("stroke", "rgba(0, 0, 0, 0.1)")
            .attr("stroke-width", 1);
    }
    
    // Add center axis lines (crosshair) - zoomable
    const axisGroup = g.append("g").attr("class", "center-axis");
    
    // Horizontal line (extended)
    axisGroup.append("line")
        .attr("x1", chartCenterX - chartMaxRadius * 2)
        .attr("y1", chartCenterY)
        .attr("x2", chartCenterX + chartMaxRadius * 2)
        .attr("y2", chartCenterY)
        .attr("stroke", "rgba(0, 0, 0, 0.15)")
        .attr("stroke-width", 1);
    
    // Vertical line (extended)
    axisGroup.append("line")
        .attr("x1", chartCenterX)
        .attr("y1", chartCenterY - chartMaxRadius * 2)
        .attr("x2", chartCenterX)
        .attr("y2", chartCenterY + chartMaxRadius * 2)
        .attr("stroke", "rgba(0, 0, 0, 0.15)")
        .attr("stroke-width", 1);

    g.append("g")
        .attr("class", "contours")
        .attr("clip-path", "url(#chart-clip)");
    
    // Create group for dots (not clipped, but will be transformed with zoom)
    dotsGroup = g.append("g")
        .attr("class", "dots");
    
    // Create group for topic cluster labels
    clustersGroup = g.append("g")
        .attr("class", "clusters");
}

function handleZoom(event) {
    const { transform } = event;
    g.attr("transform", transform);
}

function getPostsForTimeSlice(targetTimestamp) {
    const targetTime = new Date(targetTimestamp);
    const thirtyMinutesMs = 30 * 60 * 1000; // 30 minutes in milliseconds
    
    const filteredPosts = postsWithCoords.filter(post => {
        const postTime = new Date(post.created_at);
        const timeDiff = targetTime - postTime;
        return timeDiff >= 0 && timeDiff <= thirtyMinutesMs;
    });
    
    console.log(`Time slice ${targetTimestamp}: Found ${filteredPosts.length} posts in 30-minute window`);
    return filteredPosts;
}

function updateVisualization() {
    if (timeSlices.length === 0) return;
    
    const currentTime = timeSlices[currentTimeIndex];
    const currentData = dataByTime.get(currentTime);
    const currentPosts = getPostsForTimeSlice(currentTime);
    
    // Update time display
    timeDisplay.text(new Date(currentTime).toLocaleString());
    
    // Create a proper density grid from the data
    const gridSize = 70;
    const densityGrid = new Array(gridSize * gridSize).fill(0);
    
    // Find density range for color scaling
    const densityExtent = d3.extent(currentData, d => d.density);
    const densityScale = d3.scaleLinear().domain(densityExtent).range([0, 1]);
    
    currentData.forEach(d => {
        const x = Math.floor((d.x - xScale.domain()[0]) / (xScale.domain()[1] - xScale.domain()[0]) * (gridSize - 1));
        const y = Math.floor((d.y - yScale.domain()[0]) / (yScale.domain()[1] - yScale.domain()[0]) * (gridSize - 1));
        
        if (x >= 0 && x < gridSize && y >= 0 && y < gridSize) {
            densityGrid[y * gridSize + x] = Math.max(densityGrid[y * gridSize + x], d.density);
        }
    });
    
    // Generate contours
    const contours = d3.contours()
        .size([gridSize, gridSize])
        .thresholds(8);
    
    const contourData = contours(densityGrid).filter(d => d.value > 0);
    
    // Update filled contours with color grading
    const contourSelection = g.select(".contours")
        .selectAll("path")
        .data(contourData);
    
    contourSelection.exit().remove();
    
    contourSelection.enter()
        .append("path")
        .attr("class", "contour")
        .merge(contourSelection)
        .attr("d", d3.geoPath().projection(
            d3.geoTransform({
                point: function(x, y) {
                    const scaledX = xScale.domain()[0] + (x / (gridSize - 1)) * (xScale.domain()[1] - xScale.domain()[0]);
                    const scaledY = yScale.domain()[0] + (y / (gridSize - 1)) * (yScale.domain()[1] - yScale.domain()[0]);
                    this.stream.point(xScale(scaledX), yScale(scaledY));
                }
            })
        ))
        .attr("fill", d => colorScale(densityScale(d.value)))
        .attr("stroke", "black")
        .attr("stroke-width", 0.5)
        .attr("opacity", 1);
    
    // Update posts
    const postSelection = dotsGroup
        .selectAll(".post-dot")
        .data(currentPosts, d => d.uri);
    
    postSelection.exit().remove();
    
    postSelection.enter()
        .append("circle")
        .attr("class", "post-dot")
        .attr("r", 2)
        .merge(postSelection)
        .attr("cx", d => xScale(d.UMAP1))
        .attr("cy", d => yScale(d.UMAP2))
        .on("mouseover", function(event, d) {
            tooltip.transition()
                .duration(200)
                .style("opacity", .9);
            tooltip.html(`
                <div class="post-header">
                    <strong>@${d.author}</strong>
                    <span class="post-time">${new Date(d.created_at).toLocaleString()}</span>
                </div>
                <div class="post-content">
                    ${d.text.substring(0, 200)}${d.text.length > 200 ? '...' : ''}
                </div>
            `)
                .style("left", (event.pageX + 10) + "px")
                .style("top", (event.pageY - 28) + "px");
        })
        .on("mouseout", function() {
            tooltip.transition()
                .duration(500)
                .style("opacity", 0);
        });
}

function setupTimeControls() {
    // Zoom button functionality
    zoomInButton.on("click", function() {
        svg.transition().duration(300).call(
            zoom.scaleBy, 1.5
        );
    });
    
    zoomOutButton.on("click", function() {
        svg.transition().duration(300).call(
            zoom.scaleBy, 1 / 1.5
        );
    });
    
    // Play button functionality
    playButton.on("click", togglePlay);
    
    // Slider functionality
    let isDragging = false;
    
    const drag = d3.drag()
        .on("start", function() {
            isDragging = true;
            if (isPlaying) togglePlay();
        })
        .on("drag", function(event) {
            const sliderRect = slider.node().getBoundingClientRect();
            const x = Math.max(0, Math.min(sliderRect.width - 16, event.x));
            const progress = x / (sliderRect.width - 16);
            currentTimeIndex = Math.round(progress * (timeSlices.length - 1));
            updateSliderPosition();
            updateVisualization();
        })
        .on("end", function() {
            isDragging = false;
        });
    
    sliderHandle.call(drag);
    
    // Click on slider track
    slider.on("click", function(event) {
        if (event.target === slider.node()) {
            const sliderRect = slider.node().getBoundingClientRect();
            const x = event.clientX - sliderRect.left;
            const progress = Math.max(0, Math.min(1, x / sliderRect.width));
            currentTimeIndex = Math.round(progress * (timeSlices.length - 1));
            updateSliderPosition();
            updateVisualization();
        }
    });
    
    updateSliderPosition();
}

function updateSliderPosition() {
    const progress = timeSlices.length > 1 ? currentTimeIndex / (timeSlices.length - 1) : 0;
    const sliderWidth = slider.node().clientWidth;
    const handlePosition = progress * (sliderWidth - 16);
    sliderHandle.style("left", handlePosition + "px");
}

function togglePlay() {
    isPlaying = !isPlaying;
    
    if (isPlaying) {
        playButton.html('<div class="pause-icon"><div class="pause-bar"></div><div class="pause-bar"></div></div>');
        playInterval = setInterval(advanceTime, 600);
    } else {
        playButton.html('<div class="play-icon"></div>');
        clearInterval(playInterval);
    }
}

function renderTopicClusters() {
    const clusterSelection = clustersGroup
        .selectAll(".cluster-label")
        .data(topicClusters);
    
    clusterSelection.enter()
        .append("text")
        .attr("class", "cluster-label")
        .merge(clusterSelection)
        .attr("x", d => xScale(d.UMAP1))
        .attr("y", d => yScale(d.UMAP2))
        .attr("text-anchor", "middle")
        .attr("dominant-baseline", "middle")
        .style("font-size", "14px")
        .style("font-weight", "bold")
        .style("fill", "red")
        .style("stroke", "white")
        .style("stroke-width", "2px")
        .style("paint-order", "stroke")
        .text(d => d.topic);
}

function advanceTime() {
    currentTimeIndex = (currentTimeIndex + 1) % timeSlices.length;
    updateSliderPosition();
    updateVisualization();
}